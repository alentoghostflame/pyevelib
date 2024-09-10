import enum


__all__ = (
    "Datasource",
    "ESIScope",
    "Language",
    "MarketOrderType",
    "OAuthGrantType",
    "OAuthResponseType",
    "OAuthTokenType",
    "PlanetType",
)


@enum.unique
class Datasource(enum.Enum):
    tranquility = "tranquility"
    """The default, production EVE server."""


@enum.unique
class Language(enum.Enum):
    en = "en"
    """English | English"""
    en_us = "en-us"  # TODO: Think about having this automerge with en?
    """United States English | United States English
    
    Seemingly unused in the SDE, but is used by default in ESI.
    """
    de = "de"
    """Deutsch | German"""
    es = "es"
    """Español | Spanish"""
    fr = "fr"
    """Français | French"""
    ja = "ja"
    """日本語 | Japanese"""
    ko = "ko"
    """한국어 | Korean"""
    ru = "ru"
    """русский язык | Russian"""
    zh = "zh"
    """中文 | Chinese"""
    it = "it"
    """IDK? Type ID 19722 has it as straight english?"""


@enum.unique
class ESIScope(enum.Enum):
    wallet_read_character_wallet = "esi-wallet.read_character_wallet.v1"
    search_search_structures = "esi-search.search_structures.v1"
    universe_read_structures = "esi-universe.read_structures.v1"
    planets_manage_planets = "esi-planets.manage_planets.v1"
    markets_structure_markets = "esi-markets.structure_markets.v1"
    industry_read_character_jobs = "esi-industry.read_character_jobs.v1"
    industry_read_character_mining = "esi-industry.read_character_mining.v1"
    industry_read_corporation_mining = "esi-industry.read_corporation_mining.v1"


@enum.unique
class OAuthResponseType(enum.Enum):
    code = "code"


class OAuthGrantType(enum.Enum):
    refresh_token = "refresh_token"
    authorization_code = "authorization_code"


class OAuthTokenType(enum.Enum):
    bearer = "Bearer"


class PlanetType(enum.Enum):
    """Types of planets, used for Planetary Interaction."""
    barren = "barren"
    gas = "gas"
    ice = "ice"
    lava = "lava"
    oceanic = "oceanic"
    plasma = "plasma"
    storm = "storm"
    temperate = "temperate"


@enum.unique
class MarketOrderType(enum.Enum):
    buy = "buy"
    sell = "sell"
    all = "all"
