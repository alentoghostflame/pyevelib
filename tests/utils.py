from datetime import datetime, UTC

import aiohttp
import pytest
from aioresponses import aioresponses, CallbackResult
from evelib.esi import EVEESI
from evelib.esi import BASE_URL as ESI_BASE_URL
from evelib.constants import EVE_TIMESTRING_FMT
from evelib import utils as eveutils


def update_esi_headers(headers: dict) -> dict:
    """Returns ESI headers with updated timestamps."""
    output_timestring_fmt = "%a, %d %b %Y %H:%M:%S GMT"
    time_now = datetime.now(tz=UTC)
    ret = headers.copy()

    ret["Date"] = time_now.strftime(output_timestring_fmt)

    request_date = eveutils.eve_timestamp_to_datetime(headers["Date"])
    if headers["Date"] != headers["Last-Modified"]:
        mod_diff = request_date - eveutils.eve_timestamp_to_datetime(headers["Last-Modified"])
        ret["Last-Modified"] = (time_now - mod_diff).strftime(output_timestring_fmt)
    else:
        ret["Last-Modified"] = time_now.strftime(output_timestring_fmt)

    expire_diff = eveutils.eve_timestamp_to_datetime(headers["Expires"]) - request_date
    ret["Expires"] = (time_now + expire_diff).strftime(output_timestring_fmt)

    return ret

