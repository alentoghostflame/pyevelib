from evelib.universe.universe_data import UniverseLiteCache, RegionData, SolarSystemData
from pathlib import Path
import logging
from typing import Union, Optional, Set, List
import yaml
try:
    from yaml import CSafeLoader as SafeLoader, CSafeDumper as SafeDumper
except ImportError:
    from yaml import SafeLoader, SafeDumper
import os


class UniverseManager:
    def __init__(self, logger: logging.Logger, sde_path: str, cache_location: str):
        """
        Manages and handles requests about the Universe of EVE, such as Solar Systems or Regions. Constellations are not
        support at this time due to them not having real IDs and the low/non-existent usage of them in-game other than
        in the map. Does not do any web calls, relies entirely on the Static Data Export.

        :param logger: Logger object to log to.
        :param sde_path: String path to the root folder of the EVE Static Data Export
        :param cache_location: String path to the root folder to store cache files inside.
        """
        self._logger = logger
        self._sde_path = sde_path
        self._universe_path = f"{self._sde_path}/fsd/universe"
        self._cache_location = cache_location

        self._lite_cache = UniverseLiteCache(self._cache_location, "universe_lite_cache.yaml")
        self._ram_cache: dict = dict()

    def get_names(self) -> List[str]:
        return list(self._lite_cache.names.keys())

    def load(self):
        """
        Loads required files from disk. If the cache isn't on disk, populate it.
        :return:
        """
        self._logger.debug("Starting to load universe...")
        if self._lite_cache.load():
            self._logger.debug("Lite cache loaded.")
        else:
            self._logger.debug("Lite cache isn't on disk yet.")
            self._populate_lite_cache()
        self._logger.debug("Universe loaded.")

    def save(self):
        """
        Saves required files to disk. If the cache wasn't loaded from disk, save it.
        :return:
        """
        self._logger.debug("Starting to save universe...")
        if not self._lite_cache.loaded:
            self._logger.debug("Lite cache wasn't loaded from disk, saving to disk...")
            if not self._lite_cache.save():
                self._logger.warning("Lite cache was supposed to be saved, but is missing significant data, what's "
                                     "going on?")
        self._logger.debug("Universe saved.")

    def _populate_lite_cache(self):
        """
        Populates the lite cache.
        :return:
        """
        self._logger.info("Creating lite location cache from SDE, this may take some time.")
        self._logger.debug("Associating location IDs to file paths...")
        self._populate_lite_cache_ids()
        self._logger.debug("Associating location names to IDs...")
        self._populate_lite_cache_names()
        self._logger.info("Finished creating lite location cache, updates to the SDE may require deleting the cache(s) "
                          "once saved to disk.")

    def _populate_lite_cache_ids(self):
        """
        Populates the ID portion of the lite cache. This function is responsible for linking the ID of a solar system or
        region to the file location on disk. This will take some time due to PyYAML needing to interpret all the data
        and it being single-threaded. Being able to import the CSafeLoader should speed this up. Almost certainly
        possible to multi-thread this in the future.
        :return:
        """
        base_path = f"{self._sde_path}/fsd/universe"
        for space_category in get_folders_in_path(base_path):
            self._logger.debug(f"Reading space category {space_category}")
            for region_name in get_folders_in_path(f"{base_path}/{space_category}"):
                self._logger.debug(f"  Reading region {region_name}")
                region_path = f"{base_path}/{space_category}/{region_name}"

                file = open(f"{region_path}/region.staticdata", "r")
                raw_data = yaml.load(file, Loader=SafeLoader)
                file.close()
                self._lite_cache.ids[raw_data["regionID"]] = f"fsd/universe/{space_category}/{region_name}/" \
                                                             f"region.staticdata"
                for constellation_name in get_folders_in_path(region_path):
                    for solar_system_name in get_folders_in_path(f"{region_path}/{constellation_name}"):
                        solar_system_path = f"{region_path}/{constellation_name}/{solar_system_name}"

                        file = open(f"{solar_system_path}/solarsystem.staticdata", "r")
                        raw_data = yaml.load(file, Loader=SafeLoader)
                        file.close()
                        self._lite_cache.ids[raw_data["solarSystemID"]] = \
                            f"fsd/universe/{space_category}/{region_name}/{constellation_name}/{solar_system_name}" \
                            f"/solarsystem.staticdata"

    def _populate_lite_cache_names(self):
        """
        Populates the names portion of the lite cache. This function is responsible for linking the in-game name of a
        solar system or region to its ID. Due to the small size of sde/bsd/invUniqueNames.yaml, this should be
        relatively fast.
        :return:
        """
        file = open(f"{self._sde_path}/bsd/invUniqueNames.yaml", "r")
        raw_data = yaml.load(file, Loader=SafeLoader)
        file.close()

        for name_data in raw_data:
            if name_data["itemID"] in self._lite_cache.ids:
                self._lite_cache.names[name_data["itemName"]] = name_data["itemID"]

    def get_any(self, location: Union[int, str]) -> Optional[Union[RegionData, SolarSystemData]]:
        """
        A quick way to get location data. Caps and space insensitive. Recommended to use isinstance() to determine if
        returned data is a RegionData or SolarSystemData object.

        :param location: An Integer representing the ID of a solar system or region, or a String representing the name.

        :return: A RegionData object if location corresponds to a region in EVE, SolarSystemData if it corresponds to a
        solar system in EVE, None if it doesn't correspond to anything.
        """
        if isinstance(location, int):
            location_id = location
        else:
            location_id = self._lite_cache.get_id(location)

        if location_id:
            if location_id in self._ram_cache:
                return self._ram_cache[location_id]
            else:
                file_path = self._lite_cache.ids[location_id]
                if file_path.endswith("region.staticdata"):
                    location_data = RegionData(path=f"{self._sde_path}/{file_path}",
                                               name=self._lite_cache.get_name(location_id))
                elif file_path.endswith("solarsystem.staticdata"):
                    region_id = self._lite_cache.get_id(file_path.split("/")[3])
                    location_data = SolarSystemData(path=f"{self._sde_path}/{file_path}",
                                                    name=self._lite_cache.get_name(location_id), region=region_id)
                else:
                    self._logger.error(f"Path\n{file_path}\ndoesn't end with solarsystem.staticdata or "
                                       f"region.staticdata. Add proper support or put a stop to this, assuming solar "
                                       f"system.")
                    region_id = self._lite_cache.get_id(file_path.split("/")[3])
                    location_data = SolarSystemData(path=f"{self._sde_path}/{file_path}",
                                                    name=self._lite_cache.get_name(location_id), region=region_id)
                self._ram_cache[location_id] = location_data
                return self._ram_cache[location_id]
        else:
            return None


def get_folders_in_path(path: str) -> Set[str]:
    """
    Easy way to get all the folders in a specific folder.

    :param path: Path to folder to check for folders inside.

    :return: A Set of folder names inside the folder given via path.
    """
    output = set()
    for folder in os.listdir(path):
        if Path(f"{path}/{folder}").is_dir():
            output.add(folder)
    return output
