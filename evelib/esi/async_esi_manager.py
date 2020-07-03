import logging
import aiohttp
from typing import Union, Optional, Set


class ESIManager:
    def __init__(self, logger: logging.Logger):
        self._logger = logger


class AsyncESIManager:
    def __init__(self, logger: logging.Logger, session: aiohttp.ClientSession = None):
        self._logger = logger
        if session:
            self._session = session
        else:
            self._session = aiohttp.ClientSession()
        self.market = self._MarketESI(self._session)
        self.universe = self._UniverseESI(self._session)

    async def close_session(self):
        await self._session.close()

    class _MarketESI:
        def __init__(self, session: aiohttp.ClientSession):
            self._session = session
            self.BUY = "buy"
            self.SELL = "sell"
            self.ALL = "all"

        async def get_region_orders(self, region_id: Union[int, str], type_id: Union[int, str] = None,
                                    order_type: str = None) -> dict:
            base_url = "https://esi.evetech.net/latest/markets/{}/orders"
            params = {}
            if type_id:
                params["type_id"] = type_id
            if order_type:
                params["order_type"] = order_type
            response = await self._session.get(url=base_url.format(region_id), params=params)
            return await response.json()

        async def get_structure_orders(self, structure_id: Union[int, str], token: str) -> dict:
            base_url = "https://esi.evetech.net/latest/markets/structures/{}/"
            response = await self._session.get(url=base_url.format(structure_id), params={"token": token, })
            return await response.json()

    class _UniverseESI:
        def __init__(self, session: aiohttp.ClientSession):
            self._session = session

        async def get_structure_info(self, structure_id: Union[int, str], token: str) -> dict:
            base_url = "https://esi.evetech.net/latest/universe/structures/{}/"
            response = await self._session.get(url=base_url.format(structure_id), params={"token": token, })
            return await response.json()
