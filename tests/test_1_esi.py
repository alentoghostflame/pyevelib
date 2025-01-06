"""
This test file tests evelib.esi.EVEESI specific behavior, such as caching and ratelimiting.


TODO: Add autopaging test, add etag test, add param test, add oauth test.
"""

import asyncio
from datetime import datetime

import pytest
from aioresponses import aioresponses, CallbackResult
from evelib.esi import EVEESI
from evelib.esi import BASE_URL as ESI_BASE_URL

from . import utils


@pytest.fixture(name="eve_esi")
async def fixture_eve_esi() -> EVEESI:
    esi = EVEESI()
    yield esi
    await esi.close_session()


async def test_get_status(eve_esi: EVEESI):
    """Just to make sure that get_status works and isn't busted."""
    with aioresponses() as m:
        m.get(
            "https://esi.evetech.net/v2/status/",
            payload={"players": 35730, "server_version": "2755178", "start_time": "2024-11-23T11:01:11Z"},
            headers=utils.update_esi_headers(
                {
                    "Date": "Sat, 23 Nov 2024 19:35:06 GMT",
                    "Content-Type": "application/json; charset=UTF-8",
                    "Content-Length": "80",
                    "Connection": "keep-alive",
                    "Etag": '"9476e78dd6b9f9098c992d5efcf6d83b8beab9bcd464832dfb6006e1"',
                    "Expires": "Sat, 23 Nov 2024 19:35:21 GMT",
                    "Last-Modified": "Sat, 23 Nov 2024 19:34:51 GMT",
                    "X-Esi-Error-Limit-Remain": "100",
                    "X-Esi-Error-Limit-Reset": "54",
                    "X-Esi-Request-Id": "e0bed8e1-a9a3-4077-a959-d410fff1308b",
                    "PyEVELib-Test-Header": "True",
                }
            ),
        )
        res = await eve_esi.get_status()
        assert res.data["players"] == 35730

        m.assert_called_once()


async def test_error_ratelimit(eve_esi: EVEESI):
    """Test error ratelimiting, EVEESI should wait for the ESI error limit to reset before issuing more requests."""
    timeout_seconds = 0.5
    with aioresponses() as m:
        m.get(
            ESI_BASE_URL + "/v2/status/",
            payload={"players": 6666, "server_version": "2755178", "start_time": "2024-11-22T11:01:45Z"},
            # If the headers are updated to be latest, then EVEESI will notice that it hasn't expired yet and thus
            #  return immediately with the cached version, failing the time check of the test.
            headers={
                "Date": "Sat, 23 Nov 2024 19:35:06 GMT",
                "Content-Type": "application/json; charset=UTF-8",
                "Content-Length": "80",
                "Connection": "keep-alive",
                "Etag": '"9476e78dd6b9f9098c992d5efcf6d83b8beab9bcd464832dfb6006e1"',
                "Expires": "Sat, 23 Nov 2024 19:35:21 GMT",
                "Last-Modified": "Sat, 23 Nov 2024 19:34:51 GMT",
                "X-Esi-Error-Limit-Remain": "0",
                "X-Esi-Error-Limit-Reset": str(timeout_seconds),
                "X-Esi-Request-Id": "e0bed8e1-a9a3-4077-a959-d410fff1308b",
                "PyEVELib-Test-Header": "True",
            },
            repeat=True,
        )
        _ = await eve_esi.get_status()
        time_start = datetime.now()
        res = await eve_esi.get_status()
        assert timeout_seconds <= (datetime.now() - time_start).microseconds / 1000000 < timeout_seconds * 1.2
        assert res.data["players"] == 6666


async def test_cache_basic(eve_esi: EVEESI):
    """Test basic single usage cache."""
    with aioresponses() as m:
        m.get(
            "https://esi.evetech.net/v2/status/",
            payload={"players": 35602, "server_version": "2755178", "start_time": "2024-11-23T11:01:11Z"},
            headers=utils.update_esi_headers(
                {
                    "Date": "Sat, 23 Nov 2024 19:49:05 GMT",
                    "Content-Type": "application/json; charset=UTF-8",
                    "Content-Length": "80",
                    "Connection": "keep-alive",
                    "Etag": '"ab4b161e17fcac9802e509d9be346098e03f40ef304a634690e51997"',
                    "Expires": "Sat, 23 Nov 2024 19:49:23 GMT",
                    "Last-Modified": "Sat, 23 Nov 2024 19:48:53 GMT",
                    "X-Esi-Error-Limit-Remain": "100",
                    "X-Esi-Error-Limit-Reset": "55",
                    "X-Esi-Request-Id": "b225875f-c514-4421-aba3-b48112f0c096",
                    "PyEVELib-Test-Header": "True",
                }
            ),
            # Not enabling repeat, it shouldn't try to do another request.
        )
        first_res = await eve_esi.get_status()
        second_res = await eve_esi.get_status()
        assert first_res.data["players"] == 35602
        assert second_res.data["players"] == 35602
        assert first_res.id == second_res.id

        m.assert_called_once()


async def test_cache_expiry(eve_esi: EVEESI):
    """Test to make sure the requests in the cache expire correctly."""
    with aioresponses() as m:
        m.get(
            ESI_BASE_URL + "/v2/status/",
            payload={"players": 6666, "server_version": "2755178", "start_time": "2024-11-22T11:01:45Z"},
            # This is set to expire in 1 second.
            headers=utils.update_esi_headers({
                "Date": "Sat, 23 Nov 2024 19:34:01 GMT",
                "Content-Type": "application/json; charset=UTF-8",
                "Content-Length": "80",
                "Connection": "keep-alive",
                "Etag": '"9476e78dd6b9f9098c992d5efcf6d83b8beab9bcd464832dfb6006e1"',
                "Expires": "Sat, 23 Nov 2024 19:34:02 GMT",
                "Last-Modified": "Sat, 23 Nov 2024 19:34:01 GMT",
                "X-Esi-Error-Limit-Remain": "100",
                "X-Esi-Error-Limit-Reset": "55",
                "X-Esi-Request-Id": "e0bed8e1-a9a3-4077-a959-d410fff1308b",
                "PyEVELib-Test-Header": "True",
            }),
        )
        m.get(
            ESI_BASE_URL + "/v2/status/",
            payload={"players": 6667, "server_version": "2755178", "start_time": "2024-11-22T11:01:45Z"},
            headers=utils.update_esi_headers({
                "Date": "Sat, 23 Nov 2024 19:34:02 GMT",
                "Content-Type": "application/json; charset=UTF-8",
                "Content-Length": "80",
                "Connection": "keep-alive",
                "Etag": '"9476e78dd6b9f9098c992d5efcf6d83b8beab9bcd464832dfb6006e5"',
                "Expires": f"Sat, 23 Nov 2024 19:34:32 GMT",
                "Last-Modified": "Sat, 23 Nov 2024 19:34:02 GMT",
                "X-Esi-Error-Limit-Remain": "100",
                "X-Esi-Error-Limit-Reset": "54",
                "X-Esi-Request-Id": "e0bed8e1-a9a3-4077-a959-d410fff1308c",
                "PyEVELib-Test-Header": "True",
            }),
        )

        first_res = await eve_esi.get_status()
        assert first_res.data["players"] == 6666
        await asyncio.sleep(1)
        second_res = await eve_esi.get_status()
        assert second_res.id != first_res.id
        assert second_res.data["players"] == 6667
        third_res = await eve_esi.get_status()  # Just to make sure it's caching.
        assert third_res.id != first_res.id
        assert third_res.id == second_res.id
        assert third_res.data["players"] == 6667

