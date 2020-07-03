from evelib.universe import UniverseManager
from evelib.types import TypeManager
from pathlib import Path
import logging
import sys


LOGGING_FORMAT = "[{asctime}][{filename}][{lineno:3}][{funcName}][{levelname}] {message}"
LOGGING_LEVEL = logging.DEBUG


class EVEManager:
    def __init__(self, sde_path: str = "sde", cache_location: str = "cache", use_aiohttp: bool = True, session=None):
        setup_logger()
        self._logger: logging.Logger = logging.getLogger("evelib_logger")
        self._sde_path: str = sde_path
        self._cache_location: str = cache_location
        self.universe: UniverseManager = UniverseManager(self._logger, sde_path, cache_location)
        self.types: TypeManager = TypeManager(self._logger, sde_path, cache_location)
        from evelib.esi.async_esi_manager import AsyncESIManager
        if use_aiohttp:
            # from evelib.esi.async_esi_manager import AsyncESIManager
            self.esi: AsyncESIManager = AsyncESIManager(self._logger, session)
        else:
            self.esi: AsyncESIManager = None

    def load(self):
        self.universe.load()
        self.types.load()

    def save(self):
        Path(self._cache_location).mkdir(exist_ok=True)
        self.universe.save()
        self.types.save()


def setup_logger():
    logger = logging.getLogger("evelib_logger")
    log_format = logging.Formatter(LOGGING_FORMAT, style="{")
    log_console_handler = logging.StreamHandler(sys.stdout)
    log_console_handler.setFormatter(log_format)
    logger.addHandler(log_console_handler)

    logger.setLevel(LOGGING_LEVEL)
