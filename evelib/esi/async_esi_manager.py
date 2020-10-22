from evelib.types import TypeManager
from evelib.universe import UniverseManager
from evelib.esi import esi_objects
from typing import Union, Dict, List, Tuple, Optional
from datetime import datetime
import logging
# noinspection PyPackageRequirements
import aiohttp


class ESIManager:
    def __init__(self, logger: logging.Logger):
        self._logger = logger


class AsyncESIManager:
    def __init__(self, universe_manager: UniverseManager, type_manager: TypeManager, logger: logging.Logger,
                 session: aiohttp.ClientSession = None):
        """
        Manages and handles requests to access the EVE Swagger Interface. Only does web calls, does not rely on the
        Static Data Export.

        :param logger: Logger object to log to.
        :param session: ClientSession object to use. If none is provided, it will make one.
        """
        self._universe_manager = universe_manager
        self._type_manager = type_manager
        self._logger = logger
        if session:
            self._session = session
        else:
            self._session = aiohttp.ClientSession()
        self.market = MarketESI(self._universe_manager, self._type_manager, self._logger, self._session)
        self.universe = UniverseESI(self._session)
        self.industry: IndustryESI = IndustryESI(self._logger, self._type_manager, self._session)
        self.pi: PlanetaryInteractionESI = PlanetaryInteractionESI(self._logger, self._session)

    async def close_session(self):
        """
        Used to close the ClientSession object. Useful when a ClientSession object isn't provided to the class.
        :return:
        """
        await self._session.close()


class MarketESI:
    def __init__(self, universe_manager: UniverseManager, type_manager: TypeManager, logger: logging.Logger,
                 session: aiohttp.ClientSession):
        """
        Manages and handles requests to access the EVE Swagger Interface, specifically the market portion. Only does
        web calls, does not rely on the Static Data Export.

        :param session: ClientSession object to use.
        """
        self._universe_manager = universe_manager
        self._type_manager = type_manager
        self._logger = logger
        self._session = session
        self._order_cache: Dict[Tuple[int, int, str], List[dict]] = dict()
        self._expirey_tracker: Dict[Tuple[int, int, str], datetime] = dict()
        self._history_cache: Dict[Tuple[int, int], esi_objects.MarketHistory] = dict()
        self._history_tracker: Dict[Tuple[int, int], datetime] = dict()
        # self.BUY = "buy"
        # self.SELL = "sell"
        # self.ALL = "all"

    async def get_region_orders(self, region_id: Union[int, str], type_id: Union[int, str] = None,
                                order_type: str = "all", cache: bool = True) -> List[dict]:
        """
        Gets a list of orders from the given region, with the option to filter by item and order type.

        :param region_id: Integer ID of the region to query.
        :param type_id: Optional Integer or String of the item ID to get orders of.
        :param order_type: Optional String of what order types to view. Accepts "all", "buy" or "sell".
        :param cache: Boolean True to use utilize the RAM cache, False to force a call to the EVE Swagger Interface.

        :return: A List of Dictionaries, as specified by the EVE Swagger Interface.
        """
        param_tuple = (region_id, int(type_id), order_type)
        if cache and param_tuple in self._expirey_tracker and \
                self._expirey_tracker[param_tuple] > datetime.utcnow() and param_tuple in self._order_cache:
            return self._order_cache[param_tuple]
        else:
            base_url = "https://esi.evetech.net/latest/markets/{}/orders"
            params = {}
            if type_id:
                params["type_id"] = type_id
            if order_type:
                params["order_type"] = order_type
            response = await self._session.get(url=base_url.format(region_id), params=params)
            response_json = await response.json()

            if cache:
                expire_time = datetime.strptime(response.headers.getone("Expires"), "%a, %d %b %Y %H:%M:%S GMT")
                self._expirey_tracker[param_tuple] = expire_time
                self._order_cache[param_tuple] = response_json.copy()

            return response_json

    async def get_region_history(self, region_id: Union[int, str], type_id: Union[int, str],
                                 cache: bool = True) -> esi_objects.MarketHistory:
        param_tuple = (region_id, type_id)
        if cache and param_tuple in self._expirey_tracker and self._history_tracker[param_tuple] > datetime.utcnow() \
                and param_tuple in self._history_cache:
            return self._history_cache[param_tuple]
        else:
            base_url = "https://esi.evetech.net/latest/markets/{}/history"
            response = await self._session.get(url=base_url.format(region_id), params={"type_id": type_id})
            response_json = await response.json()
            location = self._universe_manager.get_any(region_id)
            item = self._type_manager.get_type(type_id)
            market_history = esi_objects.MarketHistory(location, item, response_json)

            if cache:
                expire_time = datetime.strptime(response.headers.getone("Expires"), "%a, %d %b %Y %H:%M:%S GMT")
                self._history_tracker[param_tuple] = expire_time
                self._history_cache[param_tuple] = market_history

            return market_history

    async def get_system_orders(self, region_id: Union[int, str], system_id: Union[int, str],
                                type_id: Union[int, str] = None, order_type: str = "all",
                                cache: bool = True) -> Optional[List[dict]]:
        param_tuple = (system_id, int(type_id), order_type)
        if cache and param_tuple in self._expirey_tracker and \
                self._expirey_tracker[param_tuple] > datetime.utcnow() and param_tuple in self._order_cache:
            return self._order_cache[param_tuple]
        else:
            raw_orders = await self.get_region_orders(region_id, type_id, order_type, cache)
            if raw_orders:
                trimmed_list = list()
                for market_order in raw_orders:
                    if market_order.get("system_id", 0) == system_id:
                        trimmed_list.append(market_order)
                return trimmed_list
            else:
                return None

    async def get_structure_orders(self, structure_id: Union[int, str], token: str) -> dict:
        """
        Gets market data from the given structure.

        :param structure_id: Integer or String ID of the structure to get market data from.
        :param token: String access token used for authentication. Requires
        the esi-markets.structure_markets.v1 scope.

        :return: A response, specified by the EVE Swagger Interface.
        """
        base_url = "https://esi.evetech.net/latest/markets/structures/{}/"
        response = await self._session.get(url=base_url.format(structure_id), params={"token": token, })
        return await response.json()


class UniverseESI:
    def __init__(self, session: aiohttp.ClientSession):
        """
        Manages and handles requests to access the EVE Swagger Interface, specifically the universe portion. Only
        does web calls, does not rely on the Static Data Export.

        :param session: ClientSession object to use.
        """
        self._session = session

    async def get_structure_info(self, structure_id: Union[int, str], token: str) -> dict:
        """
        Gets information about the given structure.

        :param structure_id: Integer or String ID of the structure to get information of.
        :param token: String access token used for authentication. Requires
        the esi-universe.read_structures.v1 scope.

        :return: A response, specified by the EVE Swagger Interface.
        """
        base_url = "https://esi.evetech.net/latest/universe/structures/{}/"
        response = await self._session.get(url=base_url.format(structure_id), params={"token": token, })
        return await response.json()


class IndustryESI:
    def __init__(self, logger: logging.Logger, type_manager: TypeManager, session: aiohttp.ClientSession):
        self._logger = logger
        self._type_manager = type_manager
        self._session = session

    async def get_character_jobs_raw(self, character_id: Union[int, str], token: str) -> Optional[dict]:
        base_url = "https://esi.evetech.net/latest/characters/{}/industry/jobs/"
        response = await self._session.get(url=base_url.format(character_id), params={"token": token, })
        if esi_status_interpreter(response.status):
            return await response.json()
        else:
            return None

    async def get_character_jobs(self, character_id: Union[int, str], token: str) -> \
            Optional[List[esi_objects.IndustryJob]]:
        raw_data = await self.get_character_jobs_raw(character_id, token)
        if raw_data:
            output_list = list()
            for raw_job_data in raw_data:
                output_list.append(esi_objects.IndustryJob(type_manager=self._type_manager, state=raw_job_data))
            return output_list
        else:
            return None


class PlanetaryInteractionESI:
    def __init__(self, logger: logging.Logger, session: aiohttp.ClientSession):
        self._logger = logger
        # self._universe = universe
        self._session = session

    async def get_basic_pi_raw(self, character_id: Union[int, str], token: str) -> Optional[dict]:
        base_url = "https://esi.evetech.net/latest/characters/{}/planets/"
        response = await self._session.get(url=base_url.format(character_id), params={"token": token, })
        if esi_status_interpreter(response.status):
            return await response.json()
        else:
            return None

    async def get_planet_pi_raw(self, character_id: Union[int, str], planet_id: Union[str, int], token: str) -> \
            Optional[dict]:
        base_url = f"https://esi.evetech.net/latest/characters/{character_id}/planets/{planet_id}/"
        response = await self._session.get(url=base_url.format(character_id, planet_id), params={"token": token, })
        if esi_status_interpreter(response.status):
            return await response.json()
        else:
            return None


def esi_status_interpreter(response_status: int) -> bool:
    if response_status == 200:
        return True
    elif response_status == 404:
        return False
    elif response_status == 503:
        raise esi_objects.ESIServiceUnavailable
    else:
        raise NotImplementedError(f"Received unhandled response status: {response_status}")
