from evelib.types.categories import CategoryManager
from evelib.types.groups import GroupManager
from evelib.types.type_data import TypeCache, TypeData
import logging
from typing import Union, Dict, Optional
import yaml
try:
    from yaml import CSafeLoader as SafeLoader, CSafeDumper as SafeDumper
except ImportError:
    from yaml import SafeLoader, SafeDumper


class TypeManager:
    def __init__(self, logger: logging.Logger, sde_path: str, cache_location: str):
        """
        Manages and handles requests about the types/items of EVE. Relies entirely on the static data export.

        :param logger: Logger object to log to.
        :param sde_path: String path to the root folder of the EVE Static Data Export
        :param cache_location: String path to the root folder to store cache files inside.
        """
        self._logger = logger
        self._sde_path = sde_path
        self._cache_location = cache_location

        self._cache = TypeCache(self._cache_location, "type_cache.yaml")
        self._ram_cache: Dict[int, TypeData] = dict()

        self.categories = CategoryManager(logger, sde_path)
        self.groups = GroupManager(logger, sde_path, self.categories)

    def load(self):
        """
        Loads required files from disk. If the type cache isn't on disk, populate it.
        :return:
        """
        self.categories.load()
        self.groups.load()
        self._logger.debug("Starting to load types...")
        if self._cache.load():
            self._logger.debug("Type cache loaded.")
        else:
            self._logger.debug("Type cache isn't on disk yet.")
            self._populate_cache()
        self._logger.debug("Types loaded.")

    def save(self):
        """
        Saves required files to disk. If the type cache wasn't loaded from disk, save it.
        :return:
        """
        self._logger.debug("Starting to save types...")
        if not self._cache.loaded:
            self._logger.debug("Type cache wasn't loaded from disk, saving to disk...")
            if not self._cache.save():
                self._logger.warning("Type cache was supposed to be saved, but is missing significant data, "
                                     "what's going on?")
        self._logger.debug("Types saved.")

    def _populate_cache(self):
        """
        Populates the item cache. This function is responsible for linking both the IDs to basic data and the type name
        to the IDs. This will take some time due to PyYAML needing to interpret the large amount of data present in
        typeIDs.yaml, but being able to import the CSafeLoader should speed this up. Unlike with the universe manager,
        I don't think this can be multi-threaded.
        :return:
        """
        self._logger.info("Creating type cache from SDE, this may take some time...")
        type_file_location = f"{self._sde_path}/fsd/typeIDs.yaml"
        type_file = open(type_file_location, "r")
        raw_data = yaml.load(type_file, Loader=SafeLoader)
        type_file.close()

        for type_id in raw_data:
            type_name = raw_data[type_id].get("name", {"en": "English name not found."}).get("en",
                                                                                             "Name not found in SDE.")
            self._cache.ids[type_id] = {"name": type_name,
                                        "group_id": raw_data[type_id]["groupID"],
                                        "volume": raw_data[type_id].get("volume", -1)}
            self._cache.names[type_name] = type_id
        self._logger.info("Finished creating type cache, updates to the SDE may require deleting the cache once saved "
                          "to disk.")

    def get_type(self, identifier: Union[int, str]) -> Optional[TypeData]:
        """
        A quick way to get type data. Caps and space insensitive.

        :param identifier: An Integer representing the ID of a type, or a String representing the name of a type.

        :return: A TypeData object if the identifier corresponds to a type, None if it doesn't correspond to anything.
        """
        if isinstance(identifier, int):
            type_id = identifier
        else:
            type_id = self._cache.get_id(identifier)

        if type_id:
            if type_id in self._ram_cache:
                return self._ram_cache[type_id]
            else:
                type_data = TypeData(type_id, state=self._cache.ids[type_id], group_manager=self.groups)
                self._ram_cache[type_id] = type_data
                return self._ram_cache[type_id]
        else:
            return None

    def get_names(self) -> Dict[str, int]:
        """
        Easy way to get all the type names in the cache. Be aware that changing data in the returned dictionary will
        affect everything relying on it!

        :return: Dictionary of String type names that correspond to an Integer type ID.
        """
        return self._cache.names
