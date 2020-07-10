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
        self.id = type_id
        self.name = "Default name."
        self.group_id: int = 0
        self.volume: float = 0
        self.group: Optional[GroupData] = None
        if state:
            self.from_dict(state, group_manager)

    def from_dict(self, state: dict, group_manager: GroupManager):
        if "id" in state:
            self.id = state["id"]
        self.name = state["name"]
        self.group_id = state["group_id"]
        self.volume = state["volume"]
        self.group = group_manager.get(self.group_id)


class TypeCache:
    def __init__(self, cache_location: str, cache_name: str):
        self._cache_location = cache_location
        self._cache_name = cache_name
        self.loaded: bool = False

        self.ids: Dict[int, dict] = dict()
        self.names: Dict[str, int] = dict()

    def load(self) -> bool:
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
        if self.names and self.ids:
            file = open(f"{self._cache_location}/{self._cache_name}", "w")
            yaml.dump({"ids": self.ids, "names": self.names}, file, Dumper=SafeDumper)
            file.close()
            return True
        else:
            return False

    def get_id(self, type_name: str) -> Optional[int]:
        for key_name in self.names:
            if type_name.lower() == key_name.lower() or type_name.lower() == key_name.replace(" ", "").lower():
                return self.names[key_name]
        return None
