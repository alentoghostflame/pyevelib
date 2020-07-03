from evelib.types.type_data import TypeCache, TypeData
from pathlib import Path
import logging
from typing import Union, Dict, Optional
import yaml
try:
    from yaml import CSafeLoader as SafeLoader, CSafeDumper as SafeDumper
    print("Managed to import C yaml!")
except ImportError:
    from yaml import SafeLoader, SafeDumper
    print("Import regular yaml")
import os


class TypeManager:
    def __init__(self, logger: logging.Logger, sde_path: str, cache_location: str):
        self.logger = logger
        self.sde_path = sde_path
        self.cache_location = cache_location

        self.cache = TypeCache(cache_location, "type_cache.yaml")
        self.ram_cache: Dict[int, TypeData] = dict()

    def load(self):
        self.logger.debug("Starting to load types...")
        if self.cache.load():
            self.logger.debug("Type cache loaded.")
        else:
            self.logger.debug("Type cache isn't on disk yet.")
            self._populate_cache()
        self.logger.debug("Types loaded.")

    def save(self):
        self.logger.debug("Starting to save types...")
        if not self.cache.loaded:
            self.logger.debug("Type cache wasn't loaded from disk, saving to disk...")
            if not self.cache.save():
                self.logger.warning("Type cache was supposed to be saved, but is missing significant data, "
                                    "what's going on?")
        self.logger.debug("Types saved.")

    def _populate_cache(self):
        self.logger.info("Creating type cache from SDE, this may take some time...")
        type_file_location = f"{self.sde_path}/fsd/typeIDs.yaml"
        type_file = open(type_file_location, "r")
        raw_data = yaml.safe_load(type_file)
        type_file.close()

        for type_id in raw_data:
            type_name = raw_data[type_id].get("name", {"en": "English name not found."}).get("en", "Name not found in SDE.")
            # self.cache.ids[item_id] = {"name": raw_data[item_id]["name"]["en"]}
            self.cache.ids[type_id] = {"name": type_name}
            # self.cache.names[raw_data[item_id]["name"]["en"]] = item_id
            self.cache.names[type_name] = type_id
        self.logger.info("Finished creating type cache, updates to the SDE may require deleting the cache once saved "
                         "to disk.")

    def get_type(self, identifier: Union[int, str]) -> Optional[TypeData]:
        if isinstance(identifier, int):
            type_id = identifier
        else:
            type_id = self.cache.get_id(identifier)

        if type_id:
            if type_id in self.ram_cache:
                return self.ram_cache[type_id]
            else:
                type_data = TypeData(type_id, state=self.cache.ids[type_id])
                self.ram_cache[type_id] = type_data
                return self.ram_cache[type_id]
        else:
            return None


