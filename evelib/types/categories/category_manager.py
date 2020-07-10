from typing import Dict, Optional
import logging
import yaml
try:
    from yaml import CSafeLoader as SafeLoader, CSafeDumper as SafeDumper
    print("Managed to import C yaml!")
except ImportError:
    from yaml import SafeLoader, SafeDumper
    print("Import regular yaml")


class CategoryData:
    def __init__(self, category_id: int, state: dict = None, from_sde=True):
        self.id: int = category_id
        self.name: str = "Default Category Name."
        self.published: Optional[bool] = None

        if state and from_sde:
            self.from_sde(state)

    def from_sde(self, state: dict):
        self.name = state["name"]["en"]
        self.published = bool(state["published"])


class CategoryManager:
    def __init__(self, logger: logging.Logger, sde_path: str):
        self._logger = logger
        self._sde_path = sde_path

        self._ram_cache: Dict[int, CategoryData] = dict()

    def load(self):
        self._logger.debug("Starting to load categories...")
        self._populate_ram_cache()
        self._logger.debug("Categories loaded.")

    def _populate_ram_cache(self):
        file = open(f"{self._sde_path}/fsd/categoryIDs.yaml", "r")
        raw_data = yaml.load(file, Loader=SafeLoader)
        file.close()

        for category_id in raw_data:
            category_data = CategoryData(category_id, raw_data[category_id], from_sde=True)
            self._ram_cache[category_id] = category_data

    def get(self, category_id: int) -> Optional[CategoryData]:
        return self._ram_cache.get(category_id, None)
