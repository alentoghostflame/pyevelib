from evelib.types.groups import GroupManager, GroupData
from pathlib import Path
from typing import Dict, Optional
import yaml
try:
    from yaml import CSafeLoader as SafeLoader, CSafeDumper as SafeDumper
except ImportError:
    from yaml import SafeLoader, SafeDumper


class TypeData:
    def __init__(self, type_id, state: dict = None, group_manager: GroupManager = None):
        """
        Object that allows users to easily get information about a type.

        :param type_id: Integer ID of the type.
        :param state: Dictionary object to load data from.
        :param group_manager: GroupManager object to use.
        """
        self.id = type_id
        self.name = "Default name."
        self.group_id: int = 0
        self.volume: float = 0
        self.group: Optional[GroupData] = None
        if state:
            self.from_dict(state, group_manager)

    def from_dict(self, state: dict, group_manager: GroupManager):
        """
        Loads information from a dictionary, intended for data from the type cache.

        :param state: Dictionary object to load data from.
        :param group_manager: GroupManager object to use.
        :return:
        """
        if "id" in state:
            self.id = state["id"]
        self.name = state["name"]
        self.group_id = state["group_id"]
        self.volume = state["volume"]
        self.group = group_manager.get(self.group_id)


class TypeCache:
    def __init__(self, cache_location: str, cache_name: str):
        """
        A cache to act as a lighter weight typeIDs.yaml from the Static Data Export.

        :param cache_location: String path to the root folder to store the cache file inside.
        :param cache_name: String name of the cache file, including file extension.
        """
        self._cache_location = cache_location
        self._cache_name = cache_name
        self.loaded: bool = False

        self.ids: Dict[int, dict] = dict()
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

    def get_id(self, type_name: str) -> Optional[int]:
        """
        Gets an ID from the given String type name. Caps and space insensitive.

        :param type_name: Possible String name of a type.

        :return: Integer type ID if the given type name corresponds to an ID. Otherwise, None
        """
        for key_name in self.names:
            if type_name.lower() == key_name.lower() or type_name.lower() == key_name.replace(" ", "").lower():
                return self.names[key_name]
        return None
