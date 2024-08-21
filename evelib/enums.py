import enum


__all__ = (
    "Datasource",
    "Language",
    "MarketOrderType",
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
class MarketOrderType(enum.Enum):
    buy = "buy"
    sell = "sell"
    all = "all"
