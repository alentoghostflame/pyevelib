from __future__ import annotations

from logging import getLogger
from typing import Iterable, TYPE_CHECKING

from . import errors
from . import esi
from . import objects
from .enums import MarketOrderType, ESIScope
from .objects import (
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

if TYPE_CHECKING:
    from .enums import OAuthGrantType
    from .esi import EVEOAuthTokenResponse


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
        logger.debug("HTTP hit for Markets Region History %s %s.", region_id, type_id)
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
        logger.debug("HTTP hit for Markets Region Orders %s %s %s.", region_id, order_type.value, type_id)
        ret = EVEMarketsRegionOrders.from_esi_response(
            response, self, region_id=region_id, order_type=order_type, type_id=type_id
        )
        return ret

    async def get_markets_structure(
            self,
            structure_id: int,
            access_token: esi.EVEAccessToken | str,
            autopage: bool = True,
            page: int = 1,
    ):
        response = await self.http.get_markets_structure(structure_id, access_token, autopage=autopage, page=page)
        logger.debug("HTTP hit for Markets Structure %s.", structure_id)
        ret = objects.EVEMarketsStructureOrders.from_esi_response(response, self, structure_id=structure_id)
        return ret

    # --- Planetary Interaction

    async def get_character_colonies(
        self, character_id: int, access_token: esi.EVEAccessToken | str
    ) -> list[objects.EVEPlanetaryColony]:
        """Fetches a list of all Planetary Interaction colonies the given character has.

        Does not include layout information such as pins and routes.

        Requires ESI and auth.
        """
        response = await self.http.get_character_planets(character_id, access_token)
        logger.debug("HTTP hit for Character PI Colonies %s.", character_id)
        ret = objects.EVEPlanetaryColony.from_esi_response(response, self)
        return ret

    async def get_character_colony_layout(
        self, character_id: int, planet_id: int, access_token: esi.EVEAccessToken | str
    ) -> objects.EVEPlanetaryColonyLayout:
        """Fetches the complete layout of a specific Planetary Interaction colony.

        This includes pins, links, and routes.
        """
        response = await self.http.get_character_planet(character_id, planet_id, access_token)
        logger.debug("HTTP hit for Character PI colony layout %s %s.", character_id, planet_id)
        ret = objects.EVEPlanetaryColonyLayout.from_esi_response(
            response, self, character_id=character_id, planet_id=planet_id
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

    async def get_planet(self, planet_id: int) -> objects.EVEPlanet | None:
        ret = self.sde.get_planet(planet_id)
        if ret:
            logger.debug("Cache hit for Planet ID %s", planet_id)
            return ret
        elif self._return_on_cache_miss and self.sde.loaded:
            logger.debug("Cache miss for Planet ID %s, return on cache miss enabled.", planet_id)
            return None

        try:
            response = await self.http.get_universe_planet_info(planet_id)
            logger.debug("HTTP hit for get Planet ID %s.", planet_id)
            ret = objects.EVEPlanet.from_esi_response(response, self)
            return ret
        except errors.HTTPGeneric as e:
            logger.debug("HTTP for Planet ID %s resulted in a miss, error %s.", planet_id, type(e))

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
            logger.debug("HTTP hit for Type ID %s resulted in a miss, error %s.", type_id, type(e))
            return None

    async def get_all_types(self) -> dict[int, EVEType]:
        """Currently SDE exclusive."""
        if not self.sde.loaded:
            raise errors.SDENotLoaded("This function currently requires the SDE to be loaded before using.")

        return self.sde.get_all_types()

    # --- OAuth stuff.

    async def post_oauth_token(
        self, *, auth_code: str, grant_type: OAuthGrantType | str, client_id: str, client_secret: str
    ) -> EVEOAuthTokenResponse:
        token_response = await self.http.post_oauth_token(
            auth_code=auth_code, grant_type=grant_type, client_id=client_id, client_secret=client_secret
        )
        logger.debug("HTTP hit for post oauth token %s %s.", grant_type, client_id)
        return token_response

    async def revoke_refresh_token(self, refresh_token: str, client_id: str, client_secret: str):
        return await self.http.post_revoke_refresh_token(refresh_token, client_id, client_secret)

    async def get_access_token(
        self,
        refresh_token: str,
        client_id: str,
        client_secret: str,
        scopes: list[ESIScope | str] | None = None,
    ) -> EVEOAuthTokenResponse:
        token_response = await self.http.get_access_token(refresh_token, client_id, client_secret, scopes)
        logger.debug("HTTP hit for get access token %s.", client_id)
        return token_response
