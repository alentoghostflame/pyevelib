import sys

import aiohttp


__all__ = (
    "EVE_TIMESTRING_FMT",
    "FILE_CACHE_DIR",
    "MISSING",
    "OAUTH_RESPONSE_TEMPLATE",
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

OAUTH_RESPONSE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🔒</text></svg>">
    <title>{}</title>
  </head>
  <body>
	{}
  </body>
</html>
"""
