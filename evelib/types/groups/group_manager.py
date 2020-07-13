from evelib.types.categories import CategoryManager, CategoryData
from typing import Optional
import logging
import yaml
try:
    from yaml import CSafeLoader as SafeLoader, CSafeDumper as SafeDumper
except ImportError:
    from yaml import SafeLoader, SafeDumper


class GroupData:
    def __init__(self, group_id: int, state: dict = None, category_manager: CategoryManager = None, from_sde=True):
        """
        Object that allows users to easily get information about a group.

        :param group_id: Integer ID of the group.
        :param state: Dictionary object to load data from.
        :param category_manager: CategoryManager object to use.
        :param from_sde: If the data is from the Static Data Export. Unused, should always be True.
        """
        self.id: int = group_id
        self.name: str = "Default Group Name."
        self.published: Optional[bool] = False
        self.category_id: int = 0
        self.category: Optional[CategoryData] = None

        if state and from_sde:
            self.from_sde(state, category_manager)

    def from_sde(self, state: dict, category_manager: CategoryManager):
        """
        Loads information from a dictionary, intended for data from groupIDs.yaml in the Static Data Export.
        :param state: Dictionary Object to load data from.
        :param category_manager: CategoryManager object to use.
        :return:
        """
        self.name = state["name"].get("en", "No english name found.")
        self.published = bool(state["published"])
        self.category_id = state["categoryID"]
        self.category = category_manager.get(self.category_id)


class GroupManager:
    def __init__(self, logger: logging.Logger, sde_path: str, category_manager: CategoryManager):
        """
        Manages loading and requests for groups. Relies entirely on the Static Data Export.

        :param logger: Logger object to log to.
        :param sde_path: String path to the root folder of the EVE Static Data Export.
        :param category_manager: CategoryManager object to use.
        """
        self._logger = logger
        self._sde_path = sde_path
        self._category_manager = category_manager

        self._ram_cache: dict = dict()

    def load(self):
        """
        Shortcut to populate the RAM cache.
        :return:
        """
        self._logger.debug("Started to load groups...")
        self._populate_ram_cache()
        self._logger.debug("Groups loaded.")

    def _populate_ram_cache(self):
        """
        Loads required files from disk and populates the RAM cache.
        :return:
        """
        file = open(f"{self._sde_path}/fsd/groupIDs.yaml", "r")
        raw_data = yaml.load(file, Loader=SafeLoader)
        file.close()

        for group_id in raw_data:
            group_data = GroupData(group_id, raw_data[group_id], self._category_manager, from_sde=True)
            self._ram_cache[group_id] = group_data

    def get(self, group_id: int) -> Optional[GroupData]:
        """
        Gets group data.

        :param group_id: Integer ID of a group.

        :return: A GroupData object if the given id corresponds to a category. Otherwise, None.
        """
        return self._ram_cache.get(group_id, None)
