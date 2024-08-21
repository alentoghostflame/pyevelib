import sys

import aiohttp


__all__ = (
    "EVE_TIMESTRING_FMT",
    "FILE_CACHE_DIR",
    "MISSING",
    "SDE_CHECKSUM_FILENAME",
    "SDE_FOLDER_NAME",
    "TEMP_SDE_ZIP_FILENAME",
    "USER_AGENT",
)


EVE_TIMESTRING_FMT = "%a, %d %b %Y %H:%M:%S %Z"
USER_AGENT_BASE = "PyEveLib (https://github.com/alentoghostflame/pyevelib) Python/{0[0]}.{0[1]} aiohttp/{1}"

USER_AGENT = USER_AGENT_BASE.format(sys.version_info, aiohttp.__version__)
FILE_CACHE_DIR = "./.pyevelib_cache"
TEMP_SDE_ZIP_FILENAME = ".temp_sde.zip"
SDE_CHECKSUM_FILENAME = "sde_checksum.txt"
SPACE_CACHE_FILENAME = "universe_cache.yml"
SDE_FOLDER_NAME = "sde"

MISSING = object()  # Used as a None-like sentinel value when None has a use.

