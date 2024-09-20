from __future__ import annotations

import asyncio
import datetime
from typing import TYPE_CHECKING, Iterable, Literal

from . import utils
from . import enums
from .enums import PlanetType

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
    "EVEPlanet",
    "EVEPlanetaryColony",
    "EVEPlanetaryColonyLink",
    "EVEPlanetaryColonyRoute",
    "EVEPlanetaryColonyPin",
    "EVEPlanetaryColonyLayout",
    "EVERegion",
    "EVESolarSystem",
    "EVEType",
)


LocalizedStr = dict[enums.Language, str]


class BaseEVEObject:
    requested: datetime.datetime | None
    """When the data was requested, according to the EVE server."""
    expires: datetime.datetime | None
    """When the data expires and can/should be fetched again."""
    last_modified: datetime.datetime | None
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
            enums.Language(raw_lang): desc for raw_lang, desc in data.get("description", {}).items()
        }
        ret.description = ret.localized_description.get(enums.Language.en, None)
        ret.graphic_id = data.get("graphicID", None)
        ret.group_id = data.get("groupID", None)
        ret.icon_id = data["groupID"]
        ret.id = type_id
        ret.market_group_id = data.get("marketGroupID", None)
        ret.mass = data.get("mass", None)
        ret.localized_name = {enums.Language(raw_lang): name for raw_lang, name in data["name"].items()}
        ret.name = ret.localized_name[enums.Language.en]
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
        ret.date = datetime.datetime.strptime(data["date"], "%Y-%m-%d").replace(tzinfo=datetime.UTC)
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
        ret.issued = datetime.datetime.strptime(data["issued"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=datetime.UTC
        )
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
    order_type: enums.MarketOrderType
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
        order_type: enums.MarketOrderType,
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


# --- Planetary Interaction


class EVEPlanetaryColony(BaseEVEObject):
    last_update: datetime
    """Time the colony was last updated."""
    num_pins: int
    """Number of pins (buildings) in the colony."""
    owner_id: int
    """ID of the EVE character colony owner."""
    planet_id: int
    """ID of the planet the colony is on."""
    planet_type: enums.PlanetType
    """Type of planet."""
    solar_system_id: int
    """ID of the solar system the colony is in."""
    upgrade_level: Literal[0, 1, 2, 3, 4, 5]
    """Level of the colony."""

    async def get_solarsystem(self) -> EVESolarSystem | None:
        return await self._api.get_solarsystem(self.solar_system_id)

    async def get_planet(self) -> EVEPlanet | None:
        return await self._api.get_planet(self.planet_id)

    @classmethod
    def from_esi_response(cls, response: ESIResponse, api: EVEAPI | None) -> list[EVEPlanetaryColony]:
        ret = []
        for colony_data in response.data:
            colony = cls._from_esi_response(response, api)
            # colony.last_update = utils.eve_timestamp_to_datetime(colony_data["last_update"])
            colony.last_update = datetime.datetime.fromisoformat(colony_data["last_update"])
            colony.num_pins = colony_data["num_pins"]
            colony.owner_id = colony_data["owner_id"]
            colony.planet_id = colony_data["planet_id"]  # TODO: Add get_planet()
            colony.planet_type = PlanetType(colony_data["planet_type"])
            colony.solar_system_id = colony_data["solar_system_id"]
            colony.upgrade_level = colony_data["upgrade_level"]

            ret.append(colony)

        return ret


class EVEPlanetaryColonyLink:
    _colony: EVEPlanetaryColonyLayout
    """Colony object this link is part of."""
    destination_pin_id: int
    link_level: Literal[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    """Upgrade level of the link."""
    source_pin_id: int

    @property
    def destination_pin(self) -> EVEPlanetaryColonyPin:
        return self._colony.pins[self.destination_pin_id]

    @property
    def source_pin(self) -> EVEPlanetaryColonyPin:
        return self._colony.pins[self.source_pin_id]

    @classmethod
    def from_esi_data(cls, data: dict, colony: EVEPlanetaryColonyLayout):
        ret = cls()
        ret._colony = colony
        ret.destination_pin_id = data["destination_pin_id"]
        ret.link_level = data["link_level"]
        ret.source_pin_id = data["source_pin_id"]

        return ret


class EVEPlanetaryColonyRoute:
    _colony: EVEPlanetaryColonyLayout
    """Colony object this route is part of."""
    content_type_id: int
    """ID of the Type that this route sends."""
    destination_pin_id: int
    """ID of the destination pin."""
    quantity: float
    """Amount being transferred through this route."""
    route_id: int
    """ID of this route."""
    source_pin_id: int
    """ID of the source pin."""
    # TODO: Waypoints, wtf are those?

    @property
    def destination_pin(self) -> EVEPlanetaryColonyPin:
        return self._colony.pins[self.destination_pin_id]

    @property
    def source_pin(self) -> EVEPlanetaryColonyPin:
        return self._colony.pins[self.source_pin_id]

    @classmethod
    def from_esi_data(cls, data: dict, colony: EVEPlanetaryColonyLayout):
        ret = cls()

        ret._colony = colony
        ret.content_type_id = data["content_type_id"]
        ret.destination_pin_id = data["destination_pin_id"]
        ret.quantity = data["quantity"]
        ret.route_id = data["route_id"]
        ret.source_pin_id = data["source_pin_id"]

        return ret


class EVEPlanetaryExtractorDetails:
    _pin: EVEPlanetaryColonyPin
    """Parent pin."""
    cycle_time: int | None
    """In seconds."""
    head_radius: float | None
    heads: dict[int, tuple[float, float]]
    """{head_id: (latitude, longitude)}"""
    product_type_id: int | None
    """ID of the type this extractor is producing."""
    quantity_per_cycle: int | None

    async def get_product_type(self) -> EVEType | None:
        if self.product_type_id is None:
            return None
        else:
            return await self._pin._colony._api.get_type(self.product_type_id)

    @classmethod
    def from_esi_data(cls, data: dict, pin: EVEPlanetaryColonyPin):
        ret = cls()

        ret._pin = pin
        ret.cycle_time = data.get("cycle_time")
        ret.head_radius = data.get("head_radius")
        ret.heads = {h["head_id"]: (h["latitude"], h["longitude"]) for h in data["heads"]}
        ret.product_type_id = data.get("product_type_id")
        ret.quantity_per_cycle = data.get("quantity_per_cycle")

        return ret


class EVEPlanetaryColonyPin:
    _colony: EVEPlanetaryColonyLayout
    """Colony object this route is part of."""
    contents: dict[int, int] | None
    """{type_id: amount stored} or None if not available."""
    expiry_time: datetime.datetime | None
    """Extractor Control Unit: When the installed program is finished."""
    extractor_details: EVEPlanetaryExtractorDetails | None
    """Specific details of the Extractor Control Unit. Only available if this pin is an ECU."""
    latitude: float
    longitude: float
    pin_id: int
    type_id: int

    @property
    def expired(self) -> bool:
        """True if expiry_time is None or in the past, False if it's in the future."""
        if self.expiry_time is None or self.expiry_time < datetime.datetime.now(datetime.UTC):
            return True
        else:
            return False

    async def get_type(self) -> EVEType | None:
        return await self._colony._api.get_type(self.type_id)

    @classmethod
    def from_esi_data(cls, data: dict, colony: EVEPlanetaryColonyLayout):
        ret = cls()

        ret._colony = colony
        ret.contents = {c["type_id"]: c["amount"] for c in data.get("contents", [])}
        if expiry_time := data.get("expiry_time"):
            ret.expiry_time = datetime.datetime.fromisoformat(expiry_time)
        else:
            ret.expiry_time = None

        if extractor_details := data.get("extractor_details"):
            ret.extractor_details = EVEPlanetaryExtractorDetails.from_esi_data(extractor_details, ret)
        else:
            ret.extractor_details = None

        ret.latitude = data["latitude"]
        ret.longitude = data["longitude"]
        ret.pin_id = data["pin_id"]
        ret.type_id = data["type_id"]

        return ret


class EVEPlanetaryColonyLayout(BaseEVEObject):
    _extractor_controller_ids: set[int] = {2848, 3060, 3061, 3062, 3063, 3064, 3067, 3068}
    """Hardcoded list of extractor controller IDs."""

    character_id: int
    """ID of the character who owns the colony."""
    planet_id: int
    """ID of the planet the colony is on."""
    links: list[EVEPlanetaryColonyLink]
    pins: list[EVEPlanetaryColonyPin]
    routes: list[EVEPlanetaryColonyRoute]

    @property
    def extractor_controller_pins(self) -> list[EVEPlanetaryColonyPin]:
        ret = []
        for pin in self.pins:
            if pin.type_id in self._extractor_controller_ids:
                ret.append(pin)

        return ret

    async def get_planet(self) -> EVEPlanet | None:
        return await self._api.get_planet(self.planet_id)

    @classmethod
    def from_esi_response(
        cls, response: ESIResponse, api: EVEAPI | None, *, character_id: int, planet_id: int
    ):
        ret = cls._from_esi_response(response, api)

        ret.character_id = character_id
        ret.planet_id = planet_id
        ret.links = [
            EVEPlanetaryColonyLink.from_esi_data(link_data, ret) for link_data in response.data["links"]
        ]
        ret.pins = [EVEPlanetaryColonyPin.from_esi_data(pin_data, ret) for pin_data in response.data["pins"]]
        ret.routes = [
            EVEPlanetaryColonyRoute.from_esi_data(route_data, ret) for route_data in response.data["routes"]
        ]

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
        ret.localized_name = {enums.Language.en: name}  # No language is specified, default to en.
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
        ret.localized_name = {enums.Language.en: name}
        ret.name = name
        ret.region_id = region_id
        ret.solarsystem_ids = solarsystem_ids

        return ret


class EVESolarSystem(BaseEVEObject):
    _cached_planets: dict[int, EVEPlanet]
    """{planet_id: EVEPlanet}, only populated if loaded from the SDE."""
    constellation_id: int
    id: int
    localized_name: LocalizedStr
    name: str
    planet_ids: list[int]
    security: float
    """The security status displayed in game."""
    security_class: str | None
    """Used for determining ores in system asteroid belts, maybe? Not every system has a security class."""
    star_id: int | None
    stargate_ids: list[int]
    station_ids: list[int]
    true_security: float
    """The actual precise security status."""

    async def get_constellation(self) -> EVEConstellation | None:
        return await self._api.get_constellation(self.constellation_id)

    async def get_planets(self) -> dict[int, EVEPlanet]:
        """Returns {planet_id: EVEPlanet}"""
        if self.from_sde:
            return self._cached_planets.copy()
        else:
            async with asyncio.TaskGroup() as tg:
                planet_tasks = {}
                for planet_id in self.planet_ids:
                    planet_tasks[planet_id] = tg.create_task(self._api.get_planet(planet_id))

            ret = {planet_id: task.result() for planet_id, task in planet_tasks.items()}
            return ret

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
        ret.planet_ids = [p["planet_id"] for p in response.data["planets"]]
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
        ret.localized_name = {enums.Language.en: name}
        ret.name = name
        ret.planet_ids = list(data["planets"].keys())
        ret._cached_planets = {}
        for planet_id in ret.planet_ids:
            ret._cached_planets[planet_id] = EVEPlanet.from_sde_data(
                data["planets"][planet_id], api, planet_id=planet_id, system_id=ret.id
            )

        ret._set_security(float(data["security"]))
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


class EVEPlanet(BaseEVEObject):
    name: str
    id: int
    position: tuple[float, float, float]
    """Position of the planet, as an (X, Y, Z) tuple."""
    system_id: int
    type_id: int

    @classmethod
    def from_esi_response(cls, response: ESIResponse, api: EVEAPI | None):
        ret = cls._from_esi_response(response, api)

        ret.name = response.data["name"]
        ret.id = response.data["planet_id"]
        pos = response.data["position"]
        ret.position = (pos["x"], pos["y"], pos["z"])
        ret.type_id = response.data["type_id"]

        return ret

    @classmethod
    def from_sde_data(cls, data: dict, api: EVEAPI, *, planet_id: int, system_id: int):
        ret = cls._from_sde_data(data, api)

        ret.name = api.sde.resolve_name(planet_id)
        ret.id = planet_id
        ret.position = tuple(data["position"])
        ret.system_id = system_id
        ret.type_id = data["typeID"]

        return ret
