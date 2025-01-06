from __future__ import annotations

import hashlib
import pathlib
import shutil
import zipfile
from datetime import datetime
from logging import getLogger
from typing import TYPE_CHECKING, TypedDict, Iterable

import aiohttp
import yaml

from . import constants, yaml_workaround, objects
from .objects import EVEConstellation, EVERegion, EVESolarSystem, EVEType, EVEUniverseResolvedIDs


if TYPE_CHECKING:
    from .api import EVEAPI

    class UniverseCacheConstellation(TypedDict):
        file: str
        region: int
        solarsystems: list[int]

    class UniverseCacheRegion(TypedDict):
        constellations: list[int]
        file: str

    class UniverseCacheSolarsystem(TypedDict):
        constellation: int
        file: str
        region: int

    class UniverseCache(TypedDict):
        constellation: dict[int, UniverseCacheConstellation]
        name: dict[str, int]
        planet: dict[int, int]
        """{planet: solarsystem}"""
        region: dict[int, UniverseCacheRegion]
        solarsystem: dict[int, UniverseCacheSolarsystem]


__all__ = ("EVESDE",)

logger = getLogger(__name__)

try:
    from yaml import CDumper as Dumper, CLoader as Loader

    logger.debug("Successfully imported pyyaml CDumper and CLoader.")
except ImportError:
    from yaml import Dumper, Loader

    logger.warning(
        "Failed to import pyyaml CDumper and CLoader, loads and dumps of YAML may take much longer."
    )


SDE_CHECKSUM_DOWNLOAD_URL = "https://eve-static-data-export.s3-eu-west-1.amazonaws.com/tranquility/checksum"
SDE_ZIP_DOWNLOAD_URL = "https://eve-static-data-export.s3-eu-west-1.amazonaws.com/tranquility/sde.zip"


class EVESDE:
    def __init__(self):
        self._blueprints: dict[int, objects.EVEBlueprint] = {}
        """Blueprint data. {blueprint_id: EVEBlueprint}"""
        self._blueprint_id_lookup: dict[int, int] = {}
        """For looking up a type ID to see if it's a blueprint. {type_id: blueprint_id}"""
        self._categories: dict[int, objects.EVECategory] = {}
        """EVE Category data, from sde/fsd/categories"""
        self._groups: dict[int, objects.EVEGroup] = {}
        """EVE Group data, from sde/fsd/groups.yaml"""
        self._types: dict[int, EVEType] = {}
        self._type_name_map: dict[str, int] = {}
        """For getting all published type names or comparing case-sensitive strings to type names. """
        self._type_id_resolve_map: dict[str, int] = {}
        """For comparing case-folded strings to type names. This does not include non-published items."""
        self._type_materials: dict[int, dict[int, int]] = {}
        """Type material data, used for reprocessing? {Item ID: {material ID: quantity, }}"""

        self._space: dict[int, EVERegion | EVEConstellation | EVESolarSystem] = {}
        """Due to ESI lumping types, systems, regions, planets, factions, etc. into "Universe", the bits that 
        specifically hold regions, constellations, and solar systems are called "space" as that's where they are. Space.
        """
        self._space_loc_cache: UniverseCache = {
            "constellation": {},
            "name": {},
            "planet": {},
            "region": {},
            "solarsystem": {},
        }
        self._space_name_map: dict[str, int] = {}
        """For getting all space names or comparing case-sensitive strings to space names."""
        self._space_id_resolve_map: dict[str, int] = {}
        """For comparing case-folded strings to space names."""
        self._inv_names: dict[int, str] = {}
        """For sde/bsd/invNames.yaml"""

        self._api: EVEAPI | None = None

        self._session: aiohttp.ClientSession | None = None
        """Used for the SDE checksum and zip downloading."""
        self._loaded: bool = False

    @property
    def loaded(self) -> bool:
        return self._loaded

    # ---- Basic getters, adders, and removers.

    def add_type(self, eve_type: EVEType):
        self._types[eve_type.id] = eve_type
        if eve_type.published:
            self._type_id_resolve_map[eve_type.name.casefold()] = eve_type.id
            self._type_name_map[eve_type.name] = eve_type.id
            for local, name in eve_type.localized_name.items():
                self._type_name_map[name] = eve_type.id
                self._type_id_resolve_map[name.casefold()] = eve_type.id

    def get_type(self, type_id: int) -> EVEType | None:
        return self._types.get(type_id)

    def get_type_names(self) -> dict[str, int]:
        return self._type_name_map.copy()

    def get_all_types(self) -> dict[int, EVEType]:
        return self._types.copy()

    def get_group_ids(self) -> list[int]:
        return list(self._groups.keys())

    def get_group(self, group_id: int) -> objects.EVEGroup | None:
        return self._groups.get(group_id)

    def get_all_groups(self) -> dict[int, objects.EVEGroup]:
        return self._groups.copy()

    def get_category_ids(self) -> list[int]:
        return list(self._categories.keys())

    def get_category(self, category_id: int) -> objects.EVECategory | None:
        return self._categories.get(category_id)

    def get_all_categories(self) -> dict[int, objects.EVECategory]:
        return self._categories.copy()

    def get_type_materials(self, type_id: int) -> dict[EVEType, int] | None:
        if raw_materials := self._type_materials.get(type_id):
            return {self.get_type(mat_id): quantity for mat_id, quantity in raw_materials.items()}
        else:
            return None

    def get_blueprints(self) -> dict[int, objects.EVEBlueprint]:
        """Returns a dictionary of all blueprints, with the blueprint ID as the key and EVEBlueprint as the value."""
        return self._blueprints.copy()

    def get_blueprint(self, blueprint_id: int) -> objects.EVEBlueprint | None:
        """Gets a blueprint with the given blueprint_id"""
        return self._blueprints.get(blueprint_id)

    def get_blueprint_from_type(self, type_id: int) -> objects.EVEBlueprint | None:
        """If the type given is a blueprint, it returns the data for it."""
        if bp_id := self._blueprint_id_lookup.get(type_id):
            return self._blueprints[bp_id]
        else:
            return None

    def get_region(self, region_id: int) -> EVERegion | None:
        ret = self._space.get(region_id)
        if ret is None and (r_loc_data := self._space_loc_cache["region"].get(region_id)):
            file_path = r_loc_data["file"]
            constellations = r_loc_data["constellations"]
            name = r_loc_data["name"]
            ret = self._load_sde_universe_region(pathlib.Path(file_path), constellations, name)
        elif not isinstance(ret, EVERegion):
            ret = None

        return ret

    def get_region_names(self) -> dict[str, int]:
        # This seems like cheating and not good, but hm.
        ret = {}
        for region_id in self._space_loc_cache["region"].keys():
            ret[self._inv_names[region_id]] = region_id

        return ret

    def get_constellation(self, constellation_id: int) -> EVEConstellation | None:
        ret = self._space.get(constellation_id)

        if ret is None and (c_loc_data := self._space_loc_cache["constellation"].get(constellation_id)):
            file_path = c_loc_data["file"]
            name = c_loc_data["name"]
            region_id = c_loc_data["region"]
            solarsystem_ids = c_loc_data["solarsystems"]
            ret = self._load_sde_universe_constellation(
                pathlib.Path(file_path), name, region_id, solarsystem_ids
            )
        elif not isinstance(ret, EVEConstellation):
            ret = None

        return ret

    def get_planet(self, planet_id: int) -> objects.EVEPlanet | None:
        ret = self._space.get(planet_id)

        if ret is None and (solarsystem_id := self._space_loc_cache["planet"].get(planet_id)) is not None:
            solarsystem = self.get_solarsystem(solarsystem_id)
            if solarsystem is None:
                logger.warning(
                    "Universe cache says planet %s's solarsystem is %s, but the system wasn't found?",
                    planet_id,
                    solarsystem_id,
                )
                return None
            elif (planet := solarsystem._cached_planets.get(planet_id)) is None:
                logger.warning(
                    "Universe cache says planet %s's solarsystem is %s, but the system doesn't have the planet?"
                )
                return planet
            else:
                return planet

    def get_solarsystem(self, solarsystem_id: int) -> EVESolarSystem | None:
        ret = self._space.get(solarsystem_id)

        if ret is None and (s_loc_data := self._space_loc_cache["solarsystem"].get(solarsystem_id)):
            constellation_id = s_loc_data["constellation"]
            file_path = s_loc_data["file"]
            name = s_loc_data["name"]
            ret = self._load_sde_universe_solarsystem(pathlib.Path(file_path), name, constellation_id)
        elif not isinstance(ret, EVESolarSystem):
            ret = None

        return ret

    def get_space(self, space_id: int) -> EVERegion | EVEConstellation | EVESolarSystem | None:
        return self.get_region(space_id) or self.get_constellation(space_id) or self.get_solarsystem(space_id)

    def resolve_space_id(self, name: str) -> int | None:
        return self._space_id_resolve_map.get(name.casefold(), None)

    def get_space_names(self):
        return self._space_name_map.copy()

    def resolve_type_id(self, name: str) -> int | None:
        return self._type_id_resolve_map.get(name.casefold(), None)

    def resolve_name(self, object_id: int) -> str | None:
        """Attempts to get a name for the given object id from invNames.yaml"""
        return self._inv_names.get(object_id)

    # ---- Complex getters/setters.

    def resolve_universe_ids(self, names: Iterable[str]) -> EVEUniverseResolvedIDs:
        constellations = {}
        inventory_types = {}
        regions = {}
        solarsystems = {}
        # Note: A single name can technically resolve to multiple things.
        for name in names:
            if d := self.resolve_type_id(name):
                inventory_types[name] = d
            if (d := self.resolve_space_id(name)) and (space := self.get_space(d)):
                if isinstance(space, EVEConstellation):
                    constellations[name] = space.id
                elif isinstance(space, EVERegion):
                    regions[name] = space.id
                elif isinstance(space, EVESolarSystem):
                    solarsystems[name] = space.id
                else:
                    raise TypeError(
                        f"Hit unhandled space type {space} with ID {d} when resolving name {name}"
                    )

        return EVEUniverseResolvedIDs.from_sde_data(
            inventory_types=inventory_types,
            constellations=constellations,
            regions=regions,
            systems=solarsystems,
            api=self._api,
        )

    def resolve_universe_names(self, ids: Iterable[int]):
        constellations = {}
        inventory_types = {}
        regions = {}
        solarsystems = {}
        for resolved_id in ids:
            if t := self.get_constellation(resolved_id):
                constellations[resolved_id] = self.resolve_name(resolved_id) or t.name
            if t := self.get_type(resolved_id):
                inventory_types[resolved_id] = self.resolve_name(resolved_id) or t.name
            if t := self.get_region(resolved_id):
                regions[resolved_id] = self.resolve_name(resolved_id) or t.name
            if t := self.get_solarsystem(resolved_id):
                solarsystems[resolved_id] = self.resolve_name(resolved_id) or t.name

        return objects.EVEUniverseResolvedNames.from_sde_data(
            constellations=constellations,
            inventory_types=inventory_types,
            regions=regions,
            solar_systems=solarsystems,
            api=self._api,
        )

    # ---- SDE (un)loading shenanigans.

    def load(self, api: EVEAPI | None = None, clobber_existing_data: bool = False):
        self._api = api
        sde_dir = pathlib.Path(f"{constants.FILE_CACHE_DIR}/{constants.SDE_FOLDER_NAME}")
        if not sde_dir.exists():
            raise FileNotFoundError(f'Attempted to load SDE from "{sde_dir}" but it does not exist.')

        logger.info("Loading SDE.")
        self.load_sde_blueprints(clobber_existing_data=clobber_existing_data)
        self.load_inv_names(clobber_existing_data=clobber_existing_data)
        self.load_sde_types(clobber_existing_data=clobber_existing_data)
        self.load_sde_groups(
            clobber_existing_data=clobber_existing_data
        )  # This should be run after types are loaded.
        self.load_sde_categories(
            clobber_existing_data=clobber_existing_data
        )  # This should be run after groups are loaded.
        self.load_sde_space_loc_cache(clobber_existing_data=clobber_existing_data)
        self.load_sde_type_materials(clobber_existing_data=clobber_existing_data)
        self.set_loaded()

    def set_loaded(self):
        """Manually set the SDE as loaded."""
        self._loaded = True

    def unset_loaded(self):
        """Manually set the SDE as unloaded."""
        self._loaded = False

    def load_inv_names(self, *, clobber_existing_data: bool = False):
        if not clobber_existing_data and self._inv_names:
            logger.debug("inv_names is populated and clobber_data is false, returning.")
            return

        sde_dir = pathlib.Path(f"{constants.FILE_CACHE_DIR}/{constants.SDE_FOLDER_NAME}")
        inv_names = sde_dir / "bsd" / "invNames.yaml"
        if not inv_names.exists():
            raise FileNotFoundError(f'Inv names file at "{inv_names}" does not exist.')

        logger.debug("Loading names.")
        self._inv_names.clear()
        raw_data_list = yaml_workaround.load(inv_names)

        for data in raw_data_list:
            self._inv_names[int(data["itemID"])] = data["itemName"]

    def load_sde_types(self, *, clobber_existing_data: bool = False):
        if not clobber_existing_data and self._types:
            logger.debug("types is populated and clobber_data is false, returning.")
            return

        sde_dir = pathlib.Path(f"{constants.FILE_CACHE_DIR}/{constants.SDE_FOLDER_NAME}")
        type_ids_file = sde_dir / "fsd" / "types.yaml"
        if not type_ids_file.exists():
            raise FileNotFoundError(f'Type IDs file at "{type_ids_file}" does not exist.')

        self.unload_type_names()
        self.unload_types()

        logger.debug("Loading type IDs.")
        type_ids_data: dict[int, dict] = yaml_workaround.load(type_ids_file)

        for type_id, type_data in type_ids_data.items():
            self.add_type(EVEType.from_sde_data(type_data, self._api, type_id=type_id))

    def load_sde_space_loc_cache(self, *, clobber_existing_data: bool = False):
        if not clobber_existing_data and (
            self._space_loc_cache["constellation"]
            or self._space_loc_cache["name"]
            or self._space_loc_cache["region"]
            or self._space_loc_cache["solarsystem"]
        ):
            logger.debug("universe_loc_cache is populated and clobber_data is false, returning.")
            return

        space_cache = pathlib.Path(f"{constants.FILE_CACHE_DIR}/{constants.SPACE_CACHE_FILENAME}")
        if not space_cache.exists():
            raise FileNotFoundError(f'SDE Universe location cache file at "{space_cache}" does not exist.')

        self.unload_universe_names()
        self.unload_space_loc_cache()
        logger.debug("Loading universe location cache.")
        self._space_loc_cache = yaml_workaround.load(space_cache)
        logger.debug("Loading universe name mapping.")
        for name, uni_id in self._space_loc_cache["name"].items():
            self._space_id_resolve_map[name.casefold()] = uni_id
            self._space_name_map[name] = uni_id

    def _load_sde_universe_region(
        self, path: pathlib.Path, constellation_ids: list[int], name: str
    ) -> EVERegion:
        logger.debug('Loading SDE Universe region yaml file at "%s".', path)
        region = EVERegion.from_sde_data(
            yaml_workaround.load(path), self._api, constellation_ids=constellation_ids, name=name
        )
        self._space[region.id] = region
        return region

    def _load_sde_universe_constellation(
        self, path: pathlib.Path, name: str, region_id: int, solarsystem_ids: list[int]
    ) -> EVEConstellation:
        logger.debug('Loading SDE Universe constellation yaml file at "%s".', path)
        constellation = EVEConstellation.from_sde_data(
            yaml_workaround.load(path),
            self._api,
            name=name,
            region_id=region_id,
            solarsystem_ids=solarsystem_ids,
        )
        self._space[constellation.id] = constellation
        return constellation

    def _load_sde_universe_solarsystem(
        self,
        path: pathlib.Path,
        name: str,
        constellation_id: int,
    ) -> EVESolarSystem:
        logger.debug('Loading SDE Universe solarsystem yaml file at "%s".', path)
        solarsystem = EVESolarSystem.from_sde_data(
            yaml_workaround.load(path),
            self._api,
            name=name,
            constellation_id=constellation_id,
        )
        self._space[solarsystem.id] = solarsystem
        return solarsystem

    def load_sde_type_materials(self, *, clobber_existing_data: bool = False):
        if not clobber_existing_data and self._type_materials:
            logger.debug("type_materials is populated and clobber_data is false, returning.")
            return

        sde_dir = pathlib.Path(f"{constants.FILE_CACHE_DIR}/{constants.SDE_FOLDER_NAME}")
        type_materials_file = sde_dir / "fsd" / "typeMaterials.yaml"
        if not type_materials_file.exists():
            raise FileNotFoundError(f'Type Materials file at "{type_materials_file}" does not exist.')

        self.unload_type_materials()

        logger.debug("Loading type materials.")
        type_material_data: dict[int, dict[str, list[dict[str, int]]]] = yaml_workaround.load(
            type_materials_file
        )
        for type_id, material_list in type_material_data.items():
            self._type_materials[type_id] = {}
            for mat_data in material_list["materials"]:
                self._type_materials[type_id][mat_data["materialTypeID"]] = mat_data["quantity"]

    def load_sde_blueprints(self, *, clobber_existing_data: bool = False):
        if not clobber_existing_data and self._blueprints:
            logger.debug("blueprints is populated and clobber_data is false, returning.")
            return

        sde_dir = pathlib.Path(f"{constants.FILE_CACHE_DIR}/{constants.SDE_FOLDER_NAME}")
        blueprints_file = sde_dir / "fsd" / "blueprints.yaml"
        if not blueprints_file.exists():
            raise FileNotFoundError(f'Blueprints file at "{blueprints_file}" does not exist.')

        self.unload_blueprints()

        logger.debug("Loading blueprints.")
        blueprint_data: dict[int, dict] = yaml_workaround.load(blueprints_file)
        for bp_id, bp_data in blueprint_data.items():
            bp_obj = objects.EVEBlueprint.from_sde_data(bp_data, self._api, blueprint_id=bp_id)
            self._blueprints[bp_id] = bp_obj
            if bp_obj.type_id in self._blueprint_id_lookup:
                raise ValueError(
                    f"Tried adding blueprint type ID {bp_obj.type_id} to id_lookup, but that type ID was already set "
                    f"to {self._blueprint_id_lookup[bp_obj.type_id]}"
                )

            self._blueprint_id_lookup[bp_obj.type_id] = bp_id

    def load_sde_groups(self, *, clobber_existing_data: bool = False):
        """This needs to be run after load_sde_types for the group type_ids attribute to be populated."""
        if not clobber_existing_data and self._groups:
            logger.debug("groups are populated and clobber_existing_data is false, returning.")
            return

        sde_dir = pathlib.Path(f"{constants.FILE_CACHE_DIR}/{constants.SDE_FOLDER_NAME}")
        groups_file = sde_dir / "fsd" / "groups.yaml"
        if not groups_file.exists():
            raise FileNotFoundError(f'Groups file at "{groups_file}" does not exist.')

        self.unload_groups()

        logger.debug("Loading groups.")
        group_data = yaml_workaround.load(groups_file)

        # After groups are loaded, get type_ids ready.
        type_groups: dict[int, list[int]] = {}
        """{group_id: [type_id, type_id, ...]}"""
        if not self._types:
            logger.warning("Types are not loaded yet, groups wont know what types they have.")
        else:
            for t in self._types.values():
                if t.group_id:
                    if t.group_id not in type_groups:
                        type_groups[t.group_id] = []

                    type_groups[t.group_id].append(t.id)

        for g_id, g_data in group_data.items():
            g_object = objects.EVEGroup.from_sde_data(
                g_data, self._api, group_id=g_id, type_ids=tuple(type_groups.get(g_id, []))
            )
            self._groups[g_id] = g_object

    def load_sde_categories(self, *, clobber_existing_data: bool = False):
        """This needs to be run after load_sde_groups for the category group_ids to be populated."""
        if not clobber_existing_data and self._categories:
            logger.debug("categories are populated and clobber_existing_data is false, returning.")
            return

        sde_dir = pathlib.Path(f"{constants.FILE_CACHE_DIR}/{constants.SDE_FOLDER_NAME}")
        categories_file = sde_dir / "fsd" / "categories.yaml"
        if not categories_file.exists():
            raise FileNotFoundError(f'Categories file at "{categories_file}" dose not exist.')

        self.unload_categories()

        logger.debug("Loading categories.")
        category_data = yaml_workaround.load(categories_file)

        # After categories are loaded, get group_ids ready.
        group_categories: dict[int, list[int]] = {}
        """{category_id: [group_id, group_id, ...]}"""
        if not self._groups:
            logger.warning("Groups are not loaded yet, categories wont know what groups they have.")
        else:
            for g in self._groups.values():
                if g.category_id not in group_categories:
                    group_categories[g.category_id] = []

                group_categories[g.category_id].append(g.id)

        for c_id, c_data in category_data.items():
            c_object = objects.EVECategory.from_sde_data(
                c_data, self._api, category_id=c_id, group_ids=tuple(group_categories.get(c_id, []))
            )
            self._categories[c_id] = c_object

    def unload(self):
        """Unloads the stored data in the SDE.

        This should be used to free up memory/RAM if needed.
        This does not need to be run before the program ends.
        """
        logger.info("Unloading SDE.")
        self.unload_blueprints()
        self.unload_groups()
        self.unload_categories()
        self.unload_type_names()
        self.unload_types()
        self.unload_universe_names()
        self.unload_universe()
        self.unload_space_loc_cache()
        self.unload_inv_names()
        self.unload_type_materials()
        self.unset_loaded()

    def unload_blueprints(self):
        logger.debug("Unloading blueprints.")
        self._blueprints.clear()
        self._blueprint_id_lookup.clear()

    def unload_groups(self):
        logger.debug("Unloading groups.")
        self._groups.clear()

    def unload_categories(self):
        logger.debug("Unloading categories.")
        self._categories.clear()

    def unload_types(self):
        logger.debug("Unloading types.")
        self._types.clear()

    def unload_type_names(self):
        logger.debug("Unloading type names.")
        self._type_id_resolve_map.clear()

    def unload_universe(self):
        logger.debug("Unloading universe.")
        self._space.clear()

    def unload_space_loc_cache(self):
        logger.debug("Unloading space location cache.")
        self._space_loc_cache = {"constellation": {}, "name": {}, "region": {}, "solarsystem": {}}

    def unload_universe_names(self):
        logger.debug("Unloading space names.")
        self._space_name_map.clear()
        self._space_id_resolve_map.clear()

    def unload_inv_names(self):
        logger.debug("Unloading inv_names.")
        self._inv_names.clear()

    def unload_type_materials(self):
        logger.debug("Unloading type_materials.")
        self._type_materials.clear()

    # ---- SDE caching shenanigans.

    def generate_caches(self):
        logger.info("Generating caches.")
        self._generate_space_cache()

    @staticmethod
    def clear_caches():
        logger.info("Deleting SDE caches.")
        cache = pathlib.Path(constants.FILE_CACHE_DIR)
        universe = cache / constants.SPACE_CACHE_FILENAME
        universe.unlink(missing_ok=True)

    def _generate_space_cache(self, overwrite: bool = False):
        space_cache = pathlib.Path(f"{constants.FILE_CACHE_DIR}/{constants.SPACE_CACHE_FILENAME}")
        if space_cache.exists() and not overwrite:
            logger.debug("Space cache exists and overwrite is false, returning.")
            return

        logger.debug("Generating space file location cache.")
        if not self._inv_names:
            self.load_inv_names()

        sde_dir = pathlib.Path(f"{constants.FILE_CACHE_DIR}/{constants.SDE_FOLDER_NAME}")
        space_root = sde_dir / "universe"
        full_data: UniverseCache = {
            "name": {},
            "region": {},
            "constellation": {},
            "planet": {},
            "solarsystem": {},
        }
        # This should be abyssal, eve, void, and wormhole.
        for base in space_root.iterdir():
            # This should be the region folders in the above folders.
            for region in base.iterdir():
                #
                # --- Begin handling regions.
                #
                if region.is_dir():
                    region_data = yaml_workaround.load(region / "region.yaml")

                    region_id = region_data["regionID"]
                    if not (region_name := self._inv_names.get(region_id)):
                        logger.warning(
                            "invNames cache doesn't have the region name for ID %s, relying on folder name.",
                            region_id,
                        )
                        region_name = region.name

                    region_constellation_ids = []
                    for constellation in region.iterdir():
                        #
                        # --- Begin handling constellations
                        #
                        if constellation.is_dir():
                            constellation_data = yaml_workaround.load(constellation / "constellation.yaml")

                            constellation_id = constellation_data["constellationID"]
                            region_constellation_ids.append(constellation_id)
                            if not (constellation_name := self._inv_names.get(constellation_id)):
                                logger.warning(
                                    "invNames cache doesn't have the constellation name for ID %s, relying on "
                                    "folder name.",
                                    constellation_id,
                                )
                                constellation_name = constellation.name

                            constellation_solarsystem_ids = []
                            for solarsystem in constellation.iterdir():
                                #
                                # --- Begin handling solar systems
                                #
                                if solarsystem.is_dir():
                                    solarsystem_data = yaml_workaround.load(solarsystem / "solarsystem.yaml")

                                    solarsystem_id = solarsystem_data["solarSystemID"]
                                    constellation_solarsystem_ids.append(solarsystem_id)
                                    if not (solarsystem_name := self._inv_names.get(solarsystem_id)):
                                        logger.warning(
                                            "invNames cache doesn't have the solarsystem name for ID %s, relying "
                                            "on folder name.",
                                            solarsystem_id,
                                        )
                                        solarsystem_name = solarsystem.name

                                    if planet_data_list := solarsystem_data.get("planets"):
                                        # Begin handling planets.
                                        for planet_id, planet_data in planet_data_list.items():
                                            # TODO: Think about adding planets to the name cache?
                                            full_data["planet"][planet_id] = solarsystem_id

                                    full_data["solarsystem"][solarsystem_id] = {
                                        "constellation": constellation_id,
                                        "file": str(solarsystem) + "/solarsystem.yaml",
                                        "name": solarsystem_name,
                                        # "region": region_id,
                                    }
                                    full_data["name"][solarsystem_name] = solarsystem_id

                            full_data["constellation"][constellation_id] = {
                                "file": str(constellation) + "/constellation.yaml",
                                "name": constellation_name,
                                "region": region_id,
                                "solarsystems": constellation_solarsystem_ids,
                            }
                            full_data["name"][constellation_name] = constellation_id

                    full_data["region"][region_id] = {
                        "constellations": region_constellation_ids,
                        "file": str(region) + "/region.yaml",
                        "name": region_name,
                    }
                    full_data["name"][region_name] = region_id
                    logger.debug("Loaded region %s.", region_name)

            logger.debug("Loaded universe folder %s.", base.name)

        with open(space_cache, "w") as file:
            logger.debug("Saving universe file location cache.")
            yaml.dump(full_data, file, Dumper)

    # ---- SDE caching shenanigans end.

    # ---- SDE downloading shenanigans.

    @staticmethod
    async def _make_session() -> aiohttp.ClientSession:
        return aiohttp.ClientSession(headers={"User-Agent": constants.USER_AGENT})

    async def open_session(self):
        if self._session is None or self._session.closed:
            logger.debug("Opening session.")
            self._session = await self._make_session()

    async def close_session(self):
        if self._session and not self._session.closed:
            logger.debug("Closing session.")
            await self._session.close()

    async def update_sde(self, force=False, clear_cache_on_update: bool = True):
        logger.debug("Attempting to update SDE.")

        await self.open_session()

        cache_dir = pathlib.Path(constants.FILE_CACHE_DIR)
        # Creates cache the cache folder if needed.
        cache_dir.mkdir(parents=True, exist_ok=True)

        sde_dir = cache_dir / constants.SDE_FOLDER_NAME
        # This checks and downloads any SDE checksum updates, good to do even when force=True.
        checksum_match = await self._sde_checksum_match()

        if not sde_dir.exists():
            logger.debug('SDE folder does not exist at "%s".', sde_dir)
            should_update_sde = True
        elif force:
            logger.debug('Kwarg "force" is True.')
            should_update_sde = True
        elif checksum_match is False:
            logger.debug("SDE checksum does not match.")
            should_update_sde = True
        else:
            logger.debug('SDE folder exists, kwarg "force" is False, and checksum matches.')
            should_update_sde = False

        if should_update_sde:
            if clear_cache_on_update:
                logger.debug("Clear cache files.")
                self.clear_caches()
            logger.info("Updating local SDE.")
            await self._download_sde()
            self._unpack_sde()
            self.generate_caches()
        else:
            logger.info("Skipping SDE update.")

    async def _sde_checksum_match(self) -> bool:
        logger.debug("Downloading remote SDE checksum")
        await self.open_session()
        async with self._session.get(SDE_CHECKSUM_DOWNLOAD_URL) as response:
            remote_checksum_data = await response.read()

        local_checksum = pathlib.Path(constants.FILE_CACHE_DIR) / constants.SDE_CHECKSUM_FILENAME

        if local_checksum.exists():
            logger.debug("Found local checksum, reading it.")
            local_checksum_data = local_checksum.read_bytes()
        else:
            logger.debug('No local checksum found at "%s".', local_checksum)
            local_checksum_data = None

        if local_checksum_data == remote_checksum_data:
            logger.debug("Local and remote checksum match.")
            return True
        else:
            logger.debug(
                'Local and remote checksum don\'t match, updating local file at "%s".', local_checksum
            )
            local_checksum.write_text(remote_checksum_data.decode())
            return False

    @staticmethod
    def _temp_sde_checksum_match() -> bool:
        file_cache = pathlib.Path(constants.FILE_CACHE_DIR)
        temp_sde = file_cache / constants.TEMP_SDE_ZIP_FILENAME
        local_checksum = file_cache / constants.SDE_CHECKSUM_FILENAME

        logger.debug("Checking local temp SDE file.")
        if temp_sde.exists():
            if not local_checksum.exists():
                logger.debug('No local checksum found at "%s".', local_checksum)
                return False

            logger.debug("Calculating checksum of previously downloaded SDE.")
            md5_hash = hashlib.md5(usedforsecurity=False)
            with zipfile.ZipFile(temp_sde, "r", zipfile.ZIP_DEFLATED) as temp_sde_zip:
                file_names = temp_sde_zip.namelist()
                for file_name in file_names:
                    md5_hash.update(temp_sde_zip.read(file_name))

            temp_checksum = md5_hash.hexdigest()

            local_checksum = (file_cache / constants.SDE_CHECKSUM_FILENAME).read_text()
            if temp_checksum == local_checksum:
                logger.debug("Local checksum and temp SDE file checksum matches.")
                return True
            else:
                logger.debug("Local checksum and temp SDE file checksum does not match.")
                return False
        else:
            logger.warning("No local temp SDE file found.")
            return False

    async def _download_sde(self, ignore_local=False):
        file_cache = pathlib.Path(constants.FILE_CACHE_DIR)
        temp_sde = file_cache / constants.TEMP_SDE_ZIP_FILENAME

        if temp_sde.exists():
            logger.debug('Local temp SDE file exists at "%s".', temp_sde)
            if ignore_local:
                logger.debug(
                    'Kwarg "ignore_local" is set to True, ignoring any local file and triggering download.'
                )
                should_download_sde = True
            elif self._temp_sde_checksum_match():
                logger.debug("Local temp SDE file matches checksum, skipping download.")
                should_download_sde = False
            else:
                logger.debug("Local temp SDE file does not match local checksum, triggering download.")
                should_download_sde = True
        else:
            logger.debug("No local temp SDE, triggering download.")
            should_download_sde = True

        if should_download_sde:
            logger.info('Downloading temp SDE file to "%s", this may take some time.', temp_sde)
            chunk_size = 1 * 1024**2  # 1 Megabyte
            update_interval = 10  # In seconds.
            async with self._session.get(SDE_ZIP_DOWNLOAD_URL) as response:
                file_size = response.content_length
                current_size = 0
                time_last = datetime.now()
                with open(temp_sde, "wb") as file:
                    async for data in response.content.iter_chunked(chunk_size):
                        current_size += len(data)
                        time_now = datetime.now()
                        if (time_now - time_last).seconds >= update_interval:
                            time_last = time_now
                            if file_size is None:
                                logger.info("Downloading - %.2f MB", current_size / 1024**2)
                            else:
                                logger.info(
                                    "Downloading - (%03.2f %%) %.2f MB",
                                    current_size / file_size * 100,
                                    current_size / 1024**2,
                                )

                        file.write(data)

            logger.info("Temp SDE file download finished.")
        else:
            logger.info("Skipping temp SDE file download.")

    @staticmethod
    def _unpack_sde():
        file_cache = pathlib.Path(constants.FILE_CACHE_DIR)
        temp_sde = file_cache / constants.TEMP_SDE_ZIP_FILENAME
        sde_folder = file_cache / constants.SDE_FOLDER_NAME

        if not temp_sde.exists():
            logger.warning('Temp SDE file at "%s" does not exist, aborting.', temp_sde)
            return None

        if sde_folder.exists():
            logger.debug('Local SDE folder at "%s" exists, removing.', sde_folder)
            shutil.rmtree(sde_folder)

        logger.info('Unzipping local temp SDE file into folder "%s".', file_cache)
        with zipfile.ZipFile(temp_sde) as temp_sde_zip:
            temp_sde_zip.extractall(path=sde_folder)

        logger.info("Unzipping finished.")

        if sde_folder.exists():
            logger.debug('Sanity check passed, local SDE folder exists at "%s".', sde_folder)
        else:
            logger.error(
                'Sanity check failed, local SDE folder is supposed to exist at "%s" but does not.', sde_folder
            )

    # ---- SDE downloading shenanigans end.
