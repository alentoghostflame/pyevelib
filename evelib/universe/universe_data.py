from pathlib import Path
from typing import Dict, Optional
import yaml
try:
    from yaml import CSafeLoader as SafeLoader, CSafeDumper as SafeDumper
except ImportError:
    from yaml import SafeLoader, SafeDumper


class UniverseLiteCache:
    def __init__(self, cache_location: str, cache_name: str):
        """
        A light(ish) weight cache to act as a middle ground between querying files on disk on demand and loading all
        the universe data in the Static Data Export.

        :param cache_location: String path to the root folder to store the cache file inside.
        :param cache_name: String name of the cache file, including the file extension.
        """
        self._cache_location: str = cache_location
        self._cache_name: str = cache_name
        self.loaded: bool = False

        self.ids: Dict[int, str] = dict()
        self.names: Dict[str, int] = dict()

    def load(self) -> bool:
        """
        Reads the cache file from disk and loads contents into itself.

        :return: Boolean True if successfully loaded, False otherwise.
        """
        if Path(f"{self._cache_location}/{self._cache_name}").is_file():
            file = open(f"{self._cache_location}/{self._cache_name}", "r")
            raw_data = yaml.load(file, Loader=SafeLoader)
            file.close()
            self.ids = raw_data["ids"]
            self.names = raw_data["names"]
            self.loaded = True
            return True
        else:
            return False

    def save(self) -> bool:
        """
        Saves the file to disk assuming that self.names and self.ids have data in them.

        :return: Boolean True if successfully saved, False otherwise.
        """
        if self.names and self.ids:
            file = open(f"{self._cache_location}/{self._cache_name}", "w")
            yaml.dump({"ids": self.ids, "names": self.names}, file, Dumper=SafeDumper)
            file.close()
            return True
        else:
            return False

    def get_id(self, location_name: str) -> Optional[int]:
        """
        Gets an ID from the given String location name. Caps and space insensitive.

        :param location_name: Possible String name of a region or solar system in EVE.

        :return: Integer location ID if given name corresponds to an ID. Otherwise, None.
        """
        for key_name in self.names:
            if location_name.lower() == key_name.lower() or location_name.lower() == key_name.replace(" ", "").lower():
                return self.names[key_name]
        return None

    def get_name(self, location_id: int) -> Optional[str]:
        """
        Gets a name from the given Integer location id.

        :param location_id: Possible Integer ID of a region or solar system in EVE.

        :return: String location name if given id corresponds to a name. Otherwise, None.
        """
        for name, loc_id in self.names.items():
            if location_id == loc_id:
                return name
        return None


class RegionData:
    def __init__(self, path: str = None, state: dict = None, name: str = "Missing Name"):
        """
        Object that allows users to easily get information about a region.

        :param path: String path to file on disk to load data from.
        :param state: Dictionary object to load data from.
        :param name: String name of the region.
        """
        self.name: str = name

        self.name_id: int = 0
        self.id: int = 0

        if path:
            self.load_from_path(path)
        elif state:
            self.from_static_data(state)

    def from_static_data(self, state: dict):
        """
        Loads information from a dictionary, intended for data from a region.staticdata file in the Static Data Export.

        :param state: Dictionary object to load data from.
        :return:
        """
        self.name_id = state.get("nameID", 0)
        self.id = state.get("regionID", 0)

    def load_from_path(self, path: str):
        """
        Loads information from a file on disk, intended for reading a region.staticdata file in the Static Data Export.

        :param path: String path to file on disk.
        :return:
        """
        file = open(path, "r")
        static_state = yaml.safe_load(file)
        file.close()
        self.from_static_data(static_state)


class SolarSystemData:
    def __init__(self, path: str = None, state: dict = None, name: str = "Missing Name", region: int = 0,
                 constellation: int = 0):
        """
        Object that allows users to easily get information about a solar system.

        :param path: String path to file on disk to load data from.
        :param state: Dictionary object to load data from.
        :param name: String name of the solar system.
        :param region: Integer ID of the parent region. Not currently assigned.
        :param constellation: Integer ID of the parent constellation. Not currently assigned.
        """
        self.region: int = region
        self.constellation: int = constellation
        self.name: str = name
        self.security: int = -666
        self.planets: Dict[int, PlanetData] = dict()

        self.name_id: int = 0
        self.id: int = 0
        if path:
            self.load_from_path(path)
        elif state:
            self.from_static_data(state)

    def from_static_data(self, state: dict):
        """
        Loads information from a dictionary, intended for data from a solarsystem.staticdata file in the Static Data
        Export.

        :param state: Dictionary object to load data from.
        :return:
        """
        self.name_id = state.get("solarSystemNameID", 0)
        self.id = state.get("solarSystemID", 0)
        self.security = state.get("security", -666)
        for planet_id in state.get("planets", dict()):
            self.planets[planet_id] = PlanetData(state["planets"][planet_id], solar_system_id=self.id)

    def load_from_path(self, path: str):
        """
        Loads information from a file on disk, intended for reading a solarsystem.staticdata file in the Static Data
        Export.

        :param path: String path to file on disk.
        :return:
        """
        file = open(path, "r")
        static_data = yaml.safe_load(file)
        file.close()
        self.from_static_data(static_data)


class PlanetData:
    def __init__(self, state: dict = None, solar_system_id: int = 0):
        """
        Object that allows users to easily get information about a planet.

        :param state: Dictionary object to load data from.
        :param solar_system_id: Integer ID of parent solar system.
        """
        self.solar_system: int = solar_system_id
        self.index: int = 0

        if state:
            self.from_state(state)

    def from_state(self, state: dict):
        """
        Loads information from a dictionary, intended for data from a solarsystem.staticdata file in the Static Data
        Export.

        :param state: Dictionary object to load data from.
        :return:
        """
        self.index = state.get("celestialIndex", 0)
