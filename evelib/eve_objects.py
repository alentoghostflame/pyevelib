from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Iterable

from . import utils
from .enums import Language, MarketOrderType


if TYPE_CHECKING:
    from .api import EVEAPI
    from .esi import ESIResponse


__all__ = (
    "BaseEVEObject",
    "DogmaAttribute",
    "LocalizedStr",
    "EVEConstellation",
    "EVEMarketHistory",
    "EVEMarketOrder",
    "EVEMarketsRegionHistory",
    "EVEMarketsRegionOrders",
    "EVEUniverseResolvedIDs",
    "EVERegion",
    "EVESolarSystem",
    "EVEType",
)


LocalizedStr = dict[Language, str]


class BaseEVEObject:
    requested: datetime | None
    """When the data was requested, according to the EVE server."""
    expires: datetime | None
    """When the data expires and can/should be fetched again."""
    last_modified: datetime | None
    """When the data was last modified in EVE."""
    from_sde: bool
    """If the data was retrieved from the SDE or from ESI."""
    _api: EVEAPI

    @classmethod
    def _from_esi_response(cls, response: ESIResponse, api: EVEAPI | None):
        ret = cls()
        ret.requested = response.requested
        ret.expires = response.expires
        ret.last_modified = response.last_modified
        ret.from_sde = False
        ret._api = api

        return ret

    @classmethod
    def _from_sde_data(cls, data: dict, api: EVEAPI | None):
        ret = cls()
        ret.requested = None
        ret.expires = None
        ret.last_modified = None
        ret.from_sde = True
        ret._api = api

        return ret


# Referencing https://github.com/esi/esi-issues/issues/1103 isn't a bad idea.


class DogmaAttribute(BaseEVEObject):
    def __init__(self):
        # TODO: Finish this later, Dogma isn't super important rn as it's incomplete.
        super().__init__()
        self.attribute_id: int | None = None
        self.category_id: int | None = None


class EVEType(
    BaseEVEObject
):  # TODO: This is kinda a dumb name, think about changing it? But Eve DOES call it "Type"...
    # From types.yaml
    capacity: float | None
    description: str | None
    # dogma_attributes
    # dogma_effects
    graphic_id: int | None
    group_id: int
    icon_id: int | None
    id: int
    localized_description: LocalizedStr
    localized_name: LocalizedStr
    market_group_id: int | None
    mass: float | None
    name: str
    packaged_volume: float | None
    portion_size: int | None
    published: bool
    radius: float | None
    volume: float | None

    @classmethod
    def from_esi_response(cls, response: ESIResponse, api: EVEAPI | None):
        ret = cls._from_esi_response(response, api)
        ret.capacity = float(temp) if (temp := response.data.get("capacity")) else None
        ret.description = response.data["description"]
        ret.graphic_id = int(temp) if (temp := response.data.get("graphic_id")) else None
        ret.group_id = int(response.data["group_id"])
        ret.icon_id = int(temp) if (temp := response.data.get("icon_id")) else None
        ret.id = int(response.data["type_id"])
        ret.localized_description = {response.content_language: response.data["description"]}
        ret.localized_name = {response.content_language: response.data["name"]}
        ret.market_group_id = response.data.get("market_group_id", None)
        ret.mass = float(temp) if (temp := response.data.get("mass")) else None
        ret.name = response.data["name"]
        ret.packaged_volume = float(temp) if (temp := response.data.get("packaged_volume")) else None
        ret.portion_size = int(temp) if (temp := response.data.get("portion_size")) else None
        ret.published = response.data["published"]
        ret.radius = float(temp) if (temp := response.data.get("radius")) else None
        ret.volume = float(temp) if (temp := response.data.get("volume")) else None

        return ret

    @classmethod
    def from_sde_data(cls, data: dict, api: EVEAPI | None, *, type_id: int):
        ret = cls._from_sde_data(data, api)

        # ret.base_price = data.get("basePrice")
        ret.capacity = data.get("capacity", None)
        ret.localized_description = {
            Language(raw_lang): desc for raw_lang, desc in data.get("description", {}).items()
        }
        ret.description = ret.localized_description.get(Language.en, None)
        ret.graphic_id = data.get("graphicID", None)
        ret.group_id = data.get("groupID", None)
        ret.icon_id = data["groupID"]
        ret.id = type_id
        ret.market_group_id = data.get("marketGroupID", None)
        ret.mass = data.get("mass", None)
        ret.localized_name = {Language(raw_lang): name for raw_lang, name in data["name"].items()}
        ret.name = ret.localized_name[Language.en]
        ret.packaged_volume = None
        ret.portion_size = data.get("portionSize", None)
        ret.published = data["published"]
        ret.radius = data.get("radius", None)
        ret.volume = data.get("volume", None)

        return ret


# --- Market


class EVEMarketHistory:
    average: float
    date: datetime
    highest: float
    lowest: float
    order_count: int
    volume: int

    @classmethod
    def from_esi_data(cls, data: dict):
        ret = cls()

        ret.average = data["average"]
        ret.date = datetime.strptime(data["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        ret.highest = data["highest"]
        ret.lowest = data["lowest"]
        ret.order_count = data["order_count"]
        ret.volume = data["volume"]

        return ret


class EVEMarketsRegionHistory(BaseEVEObject):
    history: list[EVEMarketHistory]
    region_id: int
    type_id: int

    async def get_region(self):
        return await self._api.get_region(self.region_id)

    async def get_type(self):
        return await self._api.get_type(self.type_id)

    @classmethod
    def from_esi_response(cls, response: ESIResponse, api: EVEAPI | None, *, region_id: int, type_id: int):
        ret = cls._from_esi_response(response, api)

        ret.history = [EVEMarketHistory.from_esi_data(history_data) for history_data in response.data]
        ret.region_id = region_id
        ret.type_id = type_id

        return ret


class EVEMarketOrder:
    _api: EVEAPI | None
    duration: int
    id: int
    is_buy_order: bool
    issued: datetime
    location_id: int
    min_volume: int
    price: float
    range: str  # Appears to be an enum on ESI's side? Make it an enum here as well?
    system_id: int
    type_id: int
    volume_remain: int
    volume_total: int

    @classmethod
    def from_esi_data(cls, data: dict, api: EVEAPI | None):
        ret = cls()

        ret._api = api
        ret.duration = data["duration"]
        ret.is_buy_order = data["is_buy_order"]
        ret.issued = datetime.strptime(data["issued"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        ret.location_id = data["location_id"]
        ret.min_volume = data["min_volume"]
        ret.order_id = data["order_id"]
        ret.price = data["price"]
        ret.range = data["range"]
        ret.system_id = data["system_id"]
        ret.type_id = data["type_id"]
        ret.volume_remain = data["volume_remain"]
        ret.volume_total = data["volume_total"]

        return ret


class EVEMarketsRegionOrders(BaseEVEObject):
    order_type: MarketOrderType
    orders: list[EVEMarketOrder]
    region_id: int
    type_id: int | None

    async def get_region(self):
        return await self._api.get_region(self.region_id)

    async def get_type(self):
        if self.type_id is None:
            return None
        else:
            return await self._api.get_type(self.type_id)

    @classmethod
    def from_esi_response(
        cls,
        response: dict[int, ESIResponse] | ESIResponse,
        api: EVEAPI | None,
        *,
        order_type: MarketOrderType,
        region_id: int,
        type_id: int | None,
    ):
        if isinstance(response, dict):
            single_response = response[1]
        else:
            single_response = response
            response = {1: response}

        ret = cls._from_esi_response(single_response, api)

        ret.order_type = order_type
        ret.orders = []
        ret.region_id = region_id
        ret.type_id = type_id

        for res in response.values():
            for order_data in res.data:
                ret.orders.append(EVEMarketOrder.from_esi_data(order_data, ret._api))

        return ret


# --- Universe


class EVEUniverseResolvedIDs(BaseEVEObject):
    """This is for /universe/ids/, and provides mappings of name -> ID."""

    constellations: dict[str, int]
    inventory_types: dict[str, int]
    """EVE Types, items."""
    regions: dict[str, int]
    systems: dict[str, int]

    @classmethod
    def from_esi_response(cls, names: Iterable[str], response: ESIResponse, api: EVEAPI | None):
        ret = cls._from_esi_response(response, api)

        def resolve_name(o: dict[str, str]):
            co = o["name"].casefold()
            for n in names:
                if n.casefold() == co:
                    return n

            return o

        ret.constellations = {resolve_name(c): c["id"] for c in response.data.get("constellations", [])}

        ret.inventory_types = {}
        for inv_type in response.data.get("inventory_types", []):
            ret.inventory_types[resolve_name(inv_type)] = inv_type["id"]

        ret.regions = {}
        for region in response.data.get("regions", []):
            ret.regions[resolve_name(region)] = region["id"]

        ret.systems = {resolve_name(s): s["id"] for s in response.data.get("systems", [])}

        return ret

    @classmethod
    def from_sde_data(
        cls,
        *,
        constellations: dict[str, int],
        inventory_types: dict[str, int],
        regions: dict[str, int],
        systems: dict[str, int],
        api: EVEAPI | None,
    ):
        ret = cls._from_sde_data({}, api=api)

        ret.constellations = constellations
        ret.inventory_types = inventory_types
        ret.regions = regions
        ret.systems = systems

        return ret


class EVERegion(BaseEVEObject):
    constellation_ids: list[int]
    description: str | None
    id: int
    localized_name: LocalizedStr
    name: str

    async def get_constellations(self) -> list[EVEConstellation]:
        return list(
            await asyncio.gather(
                *[
                    self._api.get_constellation(constellation_id)
                    for constellation_id in self.constellation_ids
                ]
            )
        )

    @classmethod
    def from_esi_response(cls, response: ESIResponse, api: EVEAPI | None):
        ret = cls._from_esi_response(response, api)

        # ESI should return it as an int, but I don't trust it.
        ret.constellation_ids = [int(constel_id) for constel_id in response.data["constellations"]]
        ret.description = response.data["description"]
        ret.id = response.data["region_id"]
        ret.localized_name = {response.content_language: response.data["name"]}
        ret.name = response.data["name"]

        return ret

    @classmethod
    def from_sde_data(cls, data: dict, api: EVEAPI | None, *, constellation_ids: list[int], name: str):
        ret = cls._from_sde_data(data, api)

        ret.constellation_ids = constellation_ids
        ret.description = None  # There's a description ID in the SDE, but IDK where those IDs are defined.
        ret.id = int(data["regionID"])
        ret.localized_name = {Language.en: name}  # No language is specified, default to en.
        ret.name = name

        return ret


class EVEConstellation(BaseEVEObject):
    id: int
    localized_name: LocalizedStr
    name: str
    region_id: int
    solarsystem_ids: list[int]

    async def get_region(self) -> EVERegion | None:
        return await self._api.get_region(self.region_id)

    async def get_solarsystems(self) -> list[EVESolarSystem]:
        return list(
            await asyncio.gather(
                *[self._api.get_solarsystem(solarsystem_id) for solarsystem_id in self.solarsystem_ids]
            )
        )

    @classmethod
    def from_esi_response(cls, response: ESIResponse, api: EVEAPI | None):
        ret = cls._from_esi_response(response, api)

        ret.id = int(response.data["constellation_id"])
        ret.localized_name = {response.content_language: response.data["name"]}
        ret.name = response.data["name"]
        ret.region_id = int(response.data["region_id"])
        ret.solarsystem_ids = [int(solarsystem_id) for solarsystem_id in response.data["systems"]]

        return ret

    @classmethod
    def from_sde_data(
        cls, data: dict, api: EVEAPI | None, *, name: str, region_id: int, solarsystem_ids: list[int]
    ):
        ret = cls._from_sde_data(data, api)

        ret.id = int(data["constellationID"])
        ret.localized_name = {Language.en: name}
        ret.name = name
        ret.region_id = region_id
        ret.solarsystem_ids = solarsystem_ids

        return ret


class EVESolarSystem(BaseEVEObject):
    constellation_id: int
    id: int
    localized_name: LocalizedStr
    name: str
    # region_id: int | None  # ESI does not supply region ID, it has to be fetched from constellation.
    security: float
    """The security status displayed in game."""
    security_class: str | None
    """Used for determining ores in system asteroid belts, maybe? Not every system has a security class."""
    star_id: int | None
    stargate_ids: list[int]
    station_ids: list[int]
    true_security: float
    """The actual precise security status."""

    # async def get_region(self) -> EVERegion | None:
    #     pass

    async def get_constellation(self) -> EVEConstellation | None:
        return await self._api.get_constellation(self.constellation_id)

    def _set_security(self, true_security: float):
        if 0.0 < true_security < 0.05:
            self.security = 0.1
        else:
            self.security = round(true_security, 1)

    @classmethod
    def from_esi_response(cls, response: ESIResponse, api: EVEAPI | None):
        ret = cls._from_esi_response(response, api)

        ret.constellation_id = response.data["constellation_id"]
        ret.id = response.data["system_id"]
        ret.localized_name = {response.content_language: response.data["name"]}
        ret.name = response.data["name"]
        # ret.region_id = None
        ret._set_security(response.data["security_status"])
        ret.security_class = response.data.get("security_class")
        ret.star_id = response.data.get("star_id")
        ret.stargate_ids = list(response.data.get("stargates", []))
        ret.station_ids = list(response.data.get("stations", []))
        ret.true_security = response.data["security_status"]

        return ret

    @classmethod
    def from_sde_data(cls, data: dict, api: EVEAPI | None, *, constellation_id: int, name: str):
        ret = cls._from_sde_data(data, api)

        ret.constellation_id = constellation_id
        ret.id = data["solarSystemID"]
        ret.localized_name = {Language.en: name}
        ret.name = name
        ret._set_security(data["security"])
        ret.security_class = data.get("securityClass")
        ret.star_id = data.get("star", {}).get("id")
        ret.stargate_ids = list(data.get("stargates", {}).keys())
        ret.station_ids = [
            station_id
            for planet_id, planet_data in data.get("planets", {}).items()
            for station_id in planet_data.get("npcStations", {})
        ]
        ret.true_security = data["security"]

        return ret
