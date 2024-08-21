from __future__ import annotations

from datetime import datetime, timezone

from . import constants

__all__ = ("eve_timestamp_to_datetime",)


def eve_timestamp_to_datetime(timestamp: str) -> datetime:
    # I honestly have no idea wtf is going on. The "%Z" should be picking up the "GMT" in the datetime string, but
    #  it never actually gives it a timezone. It stays a timezone-naive datetime :(
    return datetime.strptime(timestamp, constants.EVE_TIMESTRING_FMT).replace(tzinfo=timezone.utc)
