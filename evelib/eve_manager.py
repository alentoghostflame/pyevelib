from evelib.universe import UniverseManager
from evelib.types import TypeManager
from pathlib import Path
import logging
import sys


LOGGING_FORMAT = "[{asctime}][{filename}][{lineno:3}][{funcName}][{levelname}] {message}"
LOGGING_LEVEL = logging.DEBUG


class EVEManager:
    def __init__(self, sde_path: str = "sde", cache_location: str = "cache", use_aiohttp: bool = True, session=None):
        """
        A developer library for quickly using the Static Data Export and EVE Swagger Interface.

        :param sde_path: String path to the root folder of the EVE Static Data Export.
        :param cache_location: String path to the root folder to store cache files inside.
        :param use_aiohttp: Boolean True to use the AIOHTTP implementation of accessing the EVE Swagger Interface, False
        for a NotImplementedError
        :param session: Session object to use for accessing the EVE Swagger Interface.
        """
        setup_logger()
        self._logger: logging.Logger = logging.getLogger("evelib_logger")
        self._sde_path: str = sde_path
        self._cache_location: str = cache_location
        self.universe: UniverseManager = UniverseManager(self._logger, sde_path, cache_location)
        self.types: TypeManager = TypeManager(self._logger, sde_path, cache_location)
        if use_aiohttp:
            from evelib.esi.async_esi_manager import AsyncESIManager
            self.esi: AsyncESIManager = AsyncESIManager(self._logger, session)
        else:
            raise NotImplementedError

    def load(self):
        """
        Loads required data from disk.
        :return:
        """
        self.universe.load()
        self.types.load()

    def save(self):
        """
        Saves required data to disk.
        :return:
        """
        Path(self._cache_location).mkdir(exist_ok=True)
        self.universe.save()
        self.types.save()


def setup_logger():
    """
    Shortcut to setup the custom logger.
    :return:
    """
    logger = logging.getLogger("evelib_logger")
    log_format = logging.Formatter(LOGGING_FORMAT, style="{")
    log_console_handler = logging.StreamHandler(sys.stdout)
    log_console_handler.setFormatter(log_format)
    logger.addHandler(log_console_handler)

    logger.setLevel(LOGGING_LEVEL)
