from evelib.types.categories import CategoryManager, CategoryData
from typing import Union, Dict, Optional
import logging
import yaml
try:
    from yaml import CSafeLoader as SafeLoader, CSafeDumper as SafeDumper
    print("Managed to import C yaml!")
except ImportError:
    from yaml import SafeLoader, SafeDumper
    print("Import regular yaml")


class GroupData:
    def __init__(self, group_id: int, state: dict = None, category_manager: CategoryManager = None, from_sde=True):
        self.id: int = group_id
        self.name: str = "Default Group Name."
        self.published: Optional[bool] = False
        self.category_id: int = 0
        self.category: Optional[CategoryData] = None

        if state and from_sde:
            self.from_sde(state, category_manager)

    def from_sde(self, state: dict, category_manager: CategoryManager):
        self.name = state["name"].get("en", "No english name found.")
        self.published = bool(state["published"])
        self.category_id = state["categoryID"]
        self.category = category_manager.get(self.category_id)


class GroupManager:
    def __init__(self, logger: logging.Logger, sde_path: str, category_manager: CategoryManager):
        self._logger = logger
        self._sde_path = sde_path
        self._category_manager = category_manager

        self._ram_cache: dict = dict()

    def load(self):
        self._logger.debug("Started to load groups...")
        self._populate_ram_cache()
        self._logger.debug("Groups loaded.")

    def _populate_ram_cache(self):
        file = open(f"{self._sde_path}/fsd/groupIDs.yaml", "r")
        raw_data = yaml.load(file, Loader=SafeLoader)
        file.close()

        for group_id in raw_data:
            group_data = GroupData(group_id, raw_data[group_id], self._category_manager, from_sde=True)
            self._ram_cache[group_id] = group_data

    def get(self, group_id: int) -> Optional[GroupData]:
        return self._ram_cache.get(group_id, None)
