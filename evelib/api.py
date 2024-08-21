from logging import getLogger
from typing import Iterable

from . import errors
from .enums import MarketOrderType
from .eve_objects import (
    EVEType,
    EVEUniverseResolvedIDs,
    EVERegion,
    EVESolarSystem,
    EVEConstellation,
    EVEMarketsRegionOrders,
    EVEMarketsRegionHistory,
)
from .sde import EVESDE
from .esi import EVEESI


__all__ = ("EVEAPI",)


logger = getLogger(__name__)


class EVEAPI:
    def __init__(self, return_on_cache_miss: bool = True):
        """

        Parameters
        ----------
        return_on_cache_miss: bool
            If the cache/SDE is loaded and a relevant getter is run (such as ``get_type()``) but fails to
            get (such as using a non-existent type ID), the getter will return None instead of making an ESI call and
            returning the results of that.
        """
        self._return_on_cache_miss = return_on_cache_miss

        self.http = EVEESI()
        self.sde = EVESDE()

    # --- EVEAPI Object stuff.

    def load_sde(self):
        self.sde.generate_caches()
        self.sde.load(self)

    def unload_sde(self):
        self.sde.unload()

    async def close(self):
        await self.http.close_session()
        await self.sde.close_session()

    # --- Market

    async def get_markets_region_history(
        self, region: EVERegion | int, eve_type: EVEType | int
    ) -> EVEMarketsRegionHistory:
        region_id = region.id if isinstance(region, EVERegion) else region
        type_id = eve_type.id if isinstance(eve_type, EVEType) else eve_type
        response = await self.http.get_markets_region_history(region_id, type_id)
        logger.debug("HTTP hit for Markets Region History %s %s", region_id, type_id)
        ret = EVEMarketsRegionHistory.from_esi_response(response, self, region_id=region_id, type_id=type_id)

        return ret

    async def get_markets_region_orders(
        self,
        region: EVERegion | int,
        order_type: MarketOrderType,
        *,
        eve_type: EVEType | int | None = None,
        autopage: bool = True,
        page: int = 1,
    ) -> EVEMarketsRegionOrders:
        region_id = region.id if isinstance(region, EVERegion) else region
        type_id = eve_type.id if isinstance(eve_type, EVEType) else eve_type
        response = await self.http.get_markets_region_orders(
            region_id, order_type, type_id=type_id, page=page, autopage=autopage
        )
        logger.debug("HTTP hit for Markets Region Orders %s %s %s", region_id, order_type.value, type_id)
        ret = EVEMarketsRegionOrders.from_esi_response(
            response, self, region_id=region_id, order_type=order_type, type_id=type_id
        )
        return ret

    # --- Universe

    async def get_type_names(self) -> dict[str, int]:
        """Currently SDE exclusive."""
        if not self.sde.loaded:
            raise errors.SDENotLoaded("This function currently requires the SDE to be loaded before using.")

        return self.sde.get_type_names()

    async def get_region_names(self) -> dict[str, int]:
        """Currently SDE exclusive."""
        if not self.sde.loaded:
            raise errors.SDENotLoaded("This function currently requires the SDE to be loaded before using.")

        return self.sde.get_region_names()

    async def get_space_names(self) -> dict[str, int]:
        """Currently SDE exclusive."""
        if not self.sde.loaded:
            raise errors.SDENotLoaded("This function currently requires the SDE to be loaded before using.")

        return self.sde.get_space_names()

    async def resolve_universe_ids(self, names: Iterable[str]) -> EVEUniverseResolvedIDs:
        """This takes a list of names and resolves them to ID's."""
        if self.sde.loaded:
            logger.debug("SDE is loaded, using it for resolving universe IDs with names %s.", names)
            return self.sde.resolve_universe_ids(names)

        try:
            response = await self.http.post_universe_ids_resolve(names=names)
            logger.debug("HTTP hit for resolving Universe IDs with names %s.", names)
            ret = EVEUniverseResolvedIDs.from_esi_response(names, response, self)
            return ret
        except errors.HTTPGeneric as e:
            logger.error("HTTP for resolving Universe IDs with names errored.", exc_info=e)
            raise e

    async def get_region(self, region_id: int) -> EVERegion | None:
        ret = self.sde.get_region(region_id)
        if ret:
            logger.debug("Cache hit for Region ID %s.", region_id)
            return ret
        elif self._return_on_cache_miss and self.sde.loaded:
            logger.debug("Cache miss for Region ID %s, return on cache miss enabled.", region_id)
            return None

        try:
            response = await self.http.get_universe_region_info(region_id)
            logger.debug("HTTP hit for Region ID %s.", region_id)
            ret = EVERegion.from_esi_response(response, self)
            return ret
        except errors.HTTPGeneric as e:
            logger.debug("HTTP for Region ID %s resulted in a miss, error %s.", region_id, type(e))
            return None

    async def get_constellation(self, constellation_id: int) -> EVEConstellation | None:
        ret = self.sde.get_constellation(constellation_id)
        if ret:
            logger.debug("Cache hit for Constellation ID %s.", constellation_id)
            return ret
        elif self._return_on_cache_miss and self.sde.loaded:
            logger.debug(
                "Cache miss for Constellation ID %s, return on cache miss enabled.", constellation_id
            )
            return None

        try:
            response = await self.http.get_universe_constellation_info(constellation_id)
            logger.debug("HTTP hit for Constellation ID %s.", constellation_id)
            ret = EVEConstellation.from_esi_response(response, self)
            return ret
        except errors.HTTPGeneric as e:
            logger.debug(
                "HTTP for Constellation ID %s resulted in a miss, error %s.", constellation_id, type(e)
            )
            return None

    async def get_solarsystem(self, solarsystem_id: int):
        ret = self.sde.get_solarsystem(solarsystem_id)
        if ret:
            logger.debug("Cache hit for Solar System ID %s.", solarsystem_id)
            return ret
        elif self._return_on_cache_miss and self.sde.loaded:
            logger.debug("Cache miss for Solar System ID %s, return on cache miss enabled.", solarsystem_id)
            return None

        try:
            response = await self.http.get_universe_solarsystem_info(solarsystem_id)
            logger.debug("HTTP hit for Solar System ID %s.", solarsystem_id)
            ret = EVESolarSystem.from_esi_response(response, self)
            return ret
        except errors.HTTPGeneric as e:
            logger.debug("HTTP for Solar System ID %s resulted in a miss, error %s.", solarsystem_id, type(e))
            return None

    async def get_type(self, type_id: int) -> EVEType | None:
        ret = self.sde.get_type(type_id)
        if ret:
            logger.debug("Cache hit for Type ID %s.", type_id)
            return ret
        elif self._return_on_cache_miss and self.sde.loaded:
            logger.debug("Cache miss for Type ID %s, return on cache miss enabled.", type_id)
            return None

        try:
            response = await self.http.get_universe_type_info(type_id)
            logger.debug("HTTP hit for Type ID %s.", type_id)
            ret = EVEType.from_esi_response(response, api=self)
            return ret
        except errors.HTTPGeneric as e:
            logger.debug("HTTP for Type ID %s resulted in a miss, error %s.", type_id, type(e))
            return None

    async def get_all_types(self) -> dict[int, EVEType]:
        """Currently SDE exclusive."""
        if not self.sde.loaded:
            raise errors.SDENotLoaded("This function currently requires the SDE to be loaded before using.")

        return self.sde.get_all_types()
