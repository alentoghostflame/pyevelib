from typing import Dict, Optional
import logging
import yaml
try:
    from yaml import CSafeLoader as SafeLoader, CSafeDumper as SafeDumper
except ImportError:
    from yaml import SafeLoader, SafeDumper


class CategoryData:
    def __init__(self, category_id: int, state: dict = None, from_sde=True):
        """
        Object that allows users to easily get information about a category.

        :param category_id: Integer ID of the category.
        :param state: Dictionary object to load data from.
        :param from_sde: If the data is from the Static Data Export. Unused, should always be True.
        """
        self.id: int = category_id
        self.name: str = "Default Category Name."
        self.published: Optional[bool] = None

        if state and from_sde:
            self.from_sde(state)

    def from_sde(self, state: dict):
        """
        Loads information from a dictionary, intended for data from categoryIDs.yaml in the Static Data Export.

        :param state: Dictionary Object to load data from.
        :return:
        """
        self.name = state["name"]["en"]
        self.published = bool(state["published"])


class CategoryManager:
    def __init__(self, logger: logging.Logger, sde_path: str):
        """
        Manages loading and requests for categories. Relies entirely on the Static Data Export.

        :param logger: Logger object to log to.
        :param sde_path: String path to the root folder of the EVE Static Data Export.
        """
        self._logger = logger
        self._sde_path = sde_path

        self._ram_cache: Dict[int, CategoryData] = dict()

    def load(self):
        """
        Shortcut to populate the RAM cache.
        :return:
        """
        self._logger.debug("Starting to load categories...")
        self._populate_ram_cache()
        self._logger.debug("Categories loaded.")

    def _populate_ram_cache(self):
        """
        Loads required files from disk and populates the RAM cache.
        :return:
        """
        file = open(f"{self._sde_path}/fsd/categoryIDs.yaml", "r")
        raw_data = yaml.load(file, Loader=SafeLoader)
        file.close()

        for category_id in raw_data:
            category_data = CategoryData(category_id, raw_data[category_id], from_sde=True)
            self._ram_cache[category_id] = category_data

    def get(self, category_id: int) -> Optional[CategoryData]:
        """
        Gets category data.

        :param category_id: Integer ID of a category.

        :return: A CategoryData object if the given id corresponds to a category. Otherwise, None.
        """
        return self._ram_cache.get(category_id, None)
