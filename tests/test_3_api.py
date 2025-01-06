"""
Tests the EVEAPI object, the bulk of the tests should be here.

Test names should be as follows: test_api_<esi or sde specific>_<EVEAPI function>

"""


from datetime import datetime, UTC

import aiohttp
import datetime
import pytest
from aioresponses import aioresponses, CallbackResult
from evelib import EVEAPI
from evelib import enums as eveenums
from evelib.esi import BASE_URL as ESI_BASE_URL
from evelib.constants import EVE_TIMESTRING_FMT
from evelib import utils as eveutils

from . import utils


@pytest.fixture(name="eve_api")
async def fixture_eve_api() -> EVEAPI:
    # TODO: Add something that tests SDE.
    api = EVEAPI()
    yield api
    await api.close()



class TestAPIESI:
    async def test_get_markets_region_history(self, eve_api):
        with aioresponses() as m:
            m.get(
                "https://esi.evetech.net/v1/markets/10000028/history?type_id=238",
                payload=[
                    {
                        "average": 374.1,
                        "date": "2024-10-13",
                        "highest": 374.1,
                        "lowest": 374.1,
                        "order_count": 1,
                        "volume": 1,
                    },
                    {
                        "average": 374.1,
                        "date": "2024-10-22",
                        "highest": 374.1,
                        "lowest": 374.1,
                        "order_count": 1,
                        "volume": 17999,
                    },
                    {
                        "average": 379.2,
                        "date": "2024-10-23",
                        "highest": 379.2,
                        "lowest": 379.2,
                        "order_count": 1,
                        "volume": 15000,
                    },
                ],
                headers=utils.update_esi_headers(
                    {
                        "Date": "Wed, 27 Nov 2024 04:15:25 GMT",
                        "Content-Type": "application/json; charset=UTF-8",
                        "Connection": "keep-alive",
                        "Etag": 'W/"5cdc9d41a0c086eb933fb5441807699f87d82f4c6d86c107cc46ec36"',
                        "Expires": "Wed, 27 Nov 2024 11:05:00 GMT",
                        "Last-Modified": "Tue, 26 Nov 2024 11:06:13 GMT",
                        "Vary": "Accept-Encoding",
                        "X-Esi-Error-Limit-Remain": "100",
                        "X-Esi-Error-Limit-Reset": "35",
                        "X-Esi-Request-Id": "6dab05dd-73c6-4c4d-b31f-bc8fcadc4785",
                        "PyEVELib-Test-Header": "True",
                    }
                ),
            )

            history = await eve_api.get_markets_region_history(10000028, 238)

            assert history.from_sde is False
            assert history.region_id == 10000028
            assert history.type_id == 238
            assert len(history.history) == 3
            assert tuple([entry.average for entry in history.history]) == (374.1, 374.1, 379.2)

            m.assert_called_once()

    async def test_get_status(self, eve_api):
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
            status = await eve_api.get_server_status()
            _ = await eve_api.get_server_status()
            assert status.from_sde == False
            assert status.players == 35730
            assert status.server_version == "2755178"
            assert status.start_time == datetime.datetime.fromisoformat("2024-11-23T11:01:11Z")

            m.assert_called_once()


class TestAPISDE:
    pass


# async def test_api_esi_get_markets_region_orders(eve_api):
#     with aioresponses() as m:
#         m.get(
#             "https://esi.evetech.net/v1/markets/10000028/history?type_id=238",
#             payload=[
#                 {
#                     "average": 374.1,
#                     "date": "2024-10-13",
#                     "highest": 374.1,
#                     "lowest": 374.1,
#                     "order_count": 1,
#                     "volume": 1,
#                 },
#                 {
#                     "average": 374.1,
#                     "date": "2024-10-22",
#                     "highest": 374.1,
#                     "lowest": 374.1,
#                     "order_count": 1,
#                     "volume": 17999,
#                 },
#                 {
#                     "average": 379.2,
#                     "date": "2024-10-23",
#                     "highest": 379.2,
#                     "lowest": 379.2,
#                     "order_count": 1,
#                     "volume": 15000,
#                 },
#             ],
#             headers=utils.update_esi_headers(
#                 {
#                     "Date": "Wed, 27 Nov 2024 04:15:25 GMT",
#                     "Content-Type": "application/json; charset=UTF-8",
#                     "Connection": "keep-alive",
#                     "Etag": 'W/"5cdc9d41a0c086eb933fb5441807699f87d82f4c6d86c107cc46ec36"',
#                     "Expires": "Wed, 27 Nov 2024 11:05:00 GMT",
#                     "Last-Modified": "Tue, 26 Nov 2024 11:06:13 GMT",
#                     "Vary": "Accept-Encoding",
#                     "X-Esi-Error-Limit-Remain": "100",
#                     "X-Esi-Error-Limit-Reset": "35",
#                     "X-Esi-Request-Id": "6dab05dd-73c6-4c4d-b31f-bc8fcadc4785",
#                     "PyEVELib-Test-Header": "True",
#                 }
#             ),
#         )
#
#         history = await eve_api.get_markets_region_history(10000028, 238)
#
#         assert history.from_sde is False
#         assert history.region_id == 10000028
#         assert history.type_id == 238
#         assert len(history.history) == 3
#         assert tuple([entry.average for entry in history.history]) == (374.1, 374.1, 379.2)
#
#         m.assert_called_once()
#
#
#
# async def test_api_esi_get_status(eve_api):
#     with aioresponses() as m:
#         m.get(
#             "https://esi.evetech.net/v2/status/",
#             payload={"players": 35730, "server_version": "2755178", "start_time": "2024-11-23T11:01:11Z"},
#             headers=utils.update_esi_headers(
#                 {
#                     "Date": "Sat, 23 Nov 2024 19:35:06 GMT",
#                     "Content-Type": "application/json; charset=UTF-8",
#                     "Content-Length": "80",
#                     "Connection": "keep-alive",
#                     "Etag": '"9476e78dd6b9f9098c992d5efcf6d83b8beab9bcd464832dfb6006e1"',
#                     "Expires": "Sat, 23 Nov 2024 19:35:21 GMT",
#                     "Last-Modified": "Sat, 23 Nov 2024 19:34:51 GMT",
#                     "X-Esi-Error-Limit-Remain": "100",
#                     "X-Esi-Error-Limit-Reset": "54",
#                     "X-Esi-Request-Id": "e0bed8e1-a9a3-4077-a959-d410fff1308b",
#                     "PyEVELib-Test-Header": "True",
#                 }
#             ),
#         )
#         status = await eve_api.get_server_status()
#         _ = await eve_api.get_server_status()
#         assert status.from_sde == False
#         assert status.players == 35730
#         assert status.server_version == "2755178"
#         assert status.start_time == datetime.datetime.fromisoformat("2024-11-23T11:01:11Z")
#
#         m.assert_called_once()

