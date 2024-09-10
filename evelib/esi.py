from __future__ import annotations

import asyncio
import base64
import datetime
import json
import urllib.parse
from datetime import timezone
from enum import Enum
from logging import getLogger
from typing import Literal

import aiohttp

from . import errors
from . import utils
from .constants import USER_AGENT
from .enums import (
    Datasource,
    ESIScope,
    Language,
    MarketOrderType,
    OAuthGrantType,
    OAuthTokenType,
)


__all__ = (
    "EVEESI",
    "EVEAccessToken",
    "ESIResponse",
    "EVEOAuthTokenResponse",
)


logger = getLogger(__name__)


BASE_URL = "https://esi.evetech.net"
OAUTH_TOKEN_URL = "https://login.eveonline.com/v2/oauth/token"
OAUTH_VERIFY_URL = "https://login.eveonline.com/oauth/verify"

DatasourceType = Literal["tranquility"]


class ESIResponse:
    headers: dict
    """Headers of the HTTP Response."""
    content_language: Language | None
    """Language of the provided content."""
    etag: str | None
    """ETag of the request."""

    def __init__(self):
        self.data: dict | None = None
        """Raw data from the request."""
        self.requested: datetime.datetime | None = None
        """When the data was requested, according to the EVE server."""
        self.expires: datetime.datetime | None = None
        """When the data expires and can/should be fetched again."""
        self.last_modified: datetime.datetime | None = None
        """When the data was last modified in EVE."""
        self.page: int | None = None
        """What page this response is for. Only populated when the response has the X-pages header."""

    @classmethod
    async def from_http_response(cls, response: aiohttp.ClientResponse, *, page: int | None):
        ret = cls()

        ret.data = await response.json()
        ret.headers = response.headers
        ret.content_language = Language(lang) if (lang := ret.headers.get("content-language")) else None
        ret.etag = ret.headers.get("etag")
        ret.request = utils.eve_timestamp_to_datetime(response.headers["date"])

        if "expires" in response.headers:
            ret.expires = utils.eve_timestamp_to_datetime(response.headers["expires"])
        else:
            ret.expires = None

        if "last-modified" in response.headers:
            ret.last_modified = utils.eve_timestamp_to_datetime(response.headers["last-modified"])
        else:
            ret.last_modified = None

        # ret.page = response.headers.get("X-Pages")
        ret.page = page

        return ret


class EVEAccessToken:
    # TODO: Add token validation? https://docs.esi.evetech.net/docs/sso/validating_eve_jwt.html

    _token: str
    """Original access_token"""
    authorized_party: str
    """Party to which this token was issued. Should be the ID of your EVE application."""
    character_name: str
    """The character name that this token grants data access to."""
    expires_at: datetime
    """Time the token expires at."""
    issued_at: datetime
    """Time the token was issued at."""
    jwt_id: str
    """ID of the JWT"""
    scopes: tuple[ESIScope]
    """ESI Scopes that this token authorizes."""
    subject: str
    """Who the token refers to. Typically "CHARACTER:EVE:<character ID>" """

    def __str__(self) -> str:
        return self._token

    @property
    def token(self) -> str:
        return self._token

    @property
    def character_id(self) -> int:
        return int(self.subject.split(":")[2])

    @classmethod
    def from_access_token(cls, access_token: str):
        ret = cls()

        header, payload, signature = access_token.split(".")
        header = base64.urlsafe_b64decode(utils.pad_base64_str(header)).decode("utf-8")
        header = json.loads(header)
        payload = base64.urlsafe_b64decode(utils.pad_base64_str(payload)).decode("utf-8")
        payload = json.loads(payload)

        ret._token = access_token
        ret.authorized_party = payload["azp"]
        ret.character_name = payload["name"]
        ret.expires_at = datetime.datetime.fromtimestamp(payload["exp"], datetime.UTC)
        ret.issued_at = datetime.datetime.fromtimestamp(payload["iat"], datetime.UTC)
        ret.jwt_id = payload["jti"]

        scopes = payload["scp"]
        if isinstance(scopes, str):
            # When it has a single scope, it's a string.
            ret.scopes = (ESIScope(scopes),)
        else:
            # When it has multiple scopes, it's a list of strings.
            ret.scopes = tuple(ESIScope(scope) for scope in scopes)

        ret.subject = payload["sub"]

        return ret


class EVEOAuthTokenResponse:
    _retrieved: datetime.datetime
    access_token: EVEAccessToken
    token_type: OAuthTokenType
    expires_in: int
    refresh_token: str

    @property
    def expired(self) -> bool:
        return (self._retrieved + datetime.timedelta(seconds=self.expires_in)) < datetime.datetime.now(
            datetime.UTC
        )

    @classmethod
    async def from_esi_response(cls, response: ESIResponse):
        ret = cls()
        ret._retrieved = response.requested or datetime.datetime.now(datetime.UTC)
        ret.access_token = EVEAccessToken.from_access_token(response.data["access_token"])
        ret.token_type = OAuthTokenType(response.data["token_type"])
        ret.expires_in = response.data["expires_in"]
        ret.refresh_token = response.data["refresh_token"]

        return ret


class ErrorRateLimit:
    def __init__(self, reset_offset: float = 0.0):
        self._reset_offset = reset_offset

        self.limit: int = 1
        self.remaining: int = 1
        self.max_concurrent: int = 1
        self.reset_after: float = 1.0

        self._reset_remaining_task: asyncio.Task | None = None
        self._on_reset_event = asyncio.Event()
        self._first_update: bool = True

        self._on_reset_event.set()

    @property
    def resetting(self) -> bool:
        return self._reset_remaining_task is not None and not self._reset_remaining_task.done()

    @property
    def empty(self) -> bool:
        return self.remaining <= 0  # Just in case a bug somehow brings it below zero.

    async def update(self, response: aiohttp.ClientResponse):
        x_remaining: int | None = (
            None if (t := response.headers.get("x-esi-error-limit-remain")) is None else int(t)
        )
        x_reset_after: float | None = (
            None
            if (t := response.headers.get("x-esi-error-limit-reset")) is None
            else float(t) + self._reset_offset
        )

        # Set the limit to the highest remaining we've received, because EVE doesn't directly tell us the limit.
        if x_remaining is None:
            self.limit = 1
            self.remaining = 1
            self.max_concurrent = 1
        elif self._first_update:
            self.remaining = x_remaining
            self.max_concurrent = x_remaining
            if self.limit < x_remaining:
                self.limit = x_remaining
        else:
            # If requests come back out of order, we should be pessimistic to avoid errors.
            self.remaining = x_remaining if x_remaining < self.remaining else self.remaining

        if self.max_concurrent < self.remaining:
            # self.remaining = self.errors_remaining
            self.max_concurrent = self.remaining

        if x_reset_after is not None:
            if self._first_update:
                self.reset_after = x_reset_after
            else:
                if self.reset_after < x_reset_after:
                    self._start_reset_task()

        if not self.resetting:
            self._start_reset_task()

        # If for whatever reason we have requests remaining but the reset event isn't set, set it.
        if 0 < self.remaining and not self._on_reset_event.is_set():
            logger.debug("Updated with remaining %s, setting reset event.", self.remaining)
            self._on_reset_event.set()

        self._first_update = False
        logger.debug(
            "Updated with limit %s, remaining %s, and reset_after %s seconds.",
            self.limit,
            self.remaining,
            self.reset_after,
        )

    async def _reset_remaining(self, time: float):
        await asyncio.sleep(time)
        self.remaining = self.limit
        self._on_reset_event.set()
        logger.debug("Reset, allowing any stopped requests to continue.")

    def _start_reset_task(self):
        if self.resetting:
            logger.debug("Reset task already running, cancelling it.")
            self._reset_remaining_task.cancel()

        loop = asyncio.get_running_loop()
        logger.debug("Resetting after %s seconds.", self.reset_after)
        self._reset_remaining_task = loop.create_task(self._reset_remaining(self.reset_after))

    def __str__(self):
        return f"<{str(self.__class__)} {self.remaining}/{self.max_concurrent} per {self.reset_after}s>"

    async def __aenter__(self):
        await self.acquire()
        return None

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.remaining += 1
        if self.max_concurrent < self.remaining:
            self.remaining = self.max_concurrent

    async def acquire(self):
        # If no more requests can be made but the event is set, clear it.
        if self.empty and self._on_reset_event.is_set():
            logger.debug("Hit the remaining request limit of %s, locking until reset.", self.limit)
            self._on_reset_event.clear()
            if not self.resetting:
                self._start_reset_task()

        # Waits in a loop for the event to be set.
        while not self._on_reset_event.is_set():
            logger.debug("Reset event isn't set, waiting.")
            await self._on_reset_event.wait()

            # Depending on the timing of events, the event can be set but the rate limit fully saturated, so
            #  we must check.
            if self.empty and self._on_reset_event.is_set():
                self._on_reset_event.clear()
                if not self.resetting:
                    self._start_reset_task()

        logger.debug("Allowing acquire.")
        self.max_concurrent -= 1
        return True


class EVEESI:
    def __init__(
        self,
        *,
        reset_offset: float = 0.0,
        use_internal_cache: bool = True,
    ):
        self._error_rate_limit = ErrorRateLimit(reset_offset=reset_offset)
        self._use_internal_cache = use_internal_cache

        self._session: aiohttp.ClientSession | None = None
        self._cache: dict[tuple[str, str, str, str], ESIResponse] = {}
        """``{(method, route, stringed headers, stringed params): EVEResponse}``"""

    async def close_session(self):
        if self._session and not self._session.closed:
            await self._session.close()

    def _make_headers(
        self,
        original_headers: dict[str, str],
        *,
        auth: str | None = None,
    ) -> dict[str, str]:
        ret = original_headers.copy()

        if "User-Agent" not in ret:
            ret["User-Agent"] = USER_AGENT

        if "Authorization" not in ret and auth is not None:
            ret["Authorization"] = auth

        return ret

    def _make_params(
        self,
        original_params: dict[str, str],
        *,
        datasource: DatasourceType | None = None,
    ) -> dict[str, str]:
        ret = original_params.copy()

        if "datasource" not in ret and datasource is not None:
            ret["datasource"] = datasource

        return ret

    async def request(
        self,
        method: str,
        route: str,
        *,
        base_url: str = BASE_URL,
        data: dict | list | str | None = None,
        json: dict | list | None = None,
        datasource: DatasourceType | None = None,
        auth: str | None = None,
        params: dict[str, str] = None,
        headers: dict[str, str] = None,
    ) -> ESIResponse:
        if data is not None and json is not None:
            raise ValueError("Only one of 'data', 'json' kwargs can be specified at once.")

        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

        params = self._make_params(params or {}, datasource=datasource)
        headers = self._make_headers(headers or {}, auth=auth)

        cache_key = (method, route, str(params), str(headers))

        if self._use_internal_cache:
            if cached_response := self._cache.get(cache_key):
                if (
                    cached_response.expires is not None
                    and datetime.datetime.now(timezone.utc) < cached_response.expires
                ):
                    logger.debug("Cached response for %s %s is within expiry, returning it.", method, route)
                    return cached_response
                elif cached_response.etag and "If-None-Match" not in headers:
                    logger.debug(
                        "Cached response for %s %s is outside expiry and has etag, putting it in headers.",
                        method,
                        route,
                    )
                    headers["If-None-Match"] = cached_response.etag

        # TODO: Think about auto-retries?
        async with self._error_rate_limit:
            logger.debug("Making request to %s %s.", method, route)
            async with self._session.request(
                method=method, url=base_url + route, data=data, json=json, params=params, headers=headers
            ) as response:
                await self._error_rate_limit.update(response)

                ret = None  # TODO: This is a patch, remove this later.

                if response.status >= 400:
                    match response.status:
                        case 400:
                            logger.warning("Error 400: Bad request for %s %s", method, route)
                            raise errors.HTTPBadRequest(response, ret)
                        case 401:
                            logger.warning("Error 401: Authorization rejected for %s %s", method, route)
                            raise errors.HTTPUnauthorized(response, ret)
                        case 403:
                            logger.warning("Error 403: Permission rejected for %s %s", method, route)
                            raise errors.HTTPForbidden(response, ret)
                        case 404:
                            logger.warning("Error 404: Couldn't find resource %s %s", method, route)
                            # TODO: Think about making 404 deny list?
                            raise errors.HTTPNotFound(response, ret)
                        case _:
                            logger.warning(
                                "Error %s: not a handled error for %s %s", response.status, method, route
                            )
                            raise errors.HTTPGeneric(response, ret)

                if warning_header := response.headers.get("Warning"):
                    if warning_header == 199:
                        logger.info("Warning 199: There is a update available for %s %s", method, route)
                    elif warning_header == 299:
                        logger.warning("Warning 299: There is a deprecation warning for %s %s", method, route)
                    else:
                        logger.warning("Warning %s: Unknown warning for %s %s", warning_header, method, route)

                if response.status == 304 and "If-None-Match" in headers:
                    logger.debug(
                        "Error 304: Not modified for %s %s with etag in headers. Returning cached response. ",
                        method,
                        route,
                    )
                    return self._cache.get(cache_key)
                else:
                    ret = await ESIResponse.from_http_response(response, page=params.get("page", None))

                if warning_text := response.headers.get("warning"):
                    if warning_text.startswith("199"):
                        logger.info("Warning 199, route update to X: %s", warning_text.split("-")[1].strip())
                    elif warning_text.startswith("299"):
                        logger.warning(
                            "Warning 299, route deprecation of X: %s", warning_text.split("-")[1].strip()
                        )

        if self._use_internal_cache and ret.expires:
            self._cache[cache_key] = ret

        return ret

    async def autopage_request(
        self,
        method: str,
        route: str,
        *,
        datasource: DatasourceType | None = None,
        auth: str | None = None,
        params: dict[str, str] = None,
        headers: dict[str, str] = None,
        max_concurrent_requests: int = 5,
    ) -> dict[int, ESIResponse]:
        concur_sema = asyncio.Semaphore(max_concurrent_requests)

        async def concurrent_request(*args, **kwargs) -> ESIResponse:
            async with concur_sema:
                return await self.request(*args, **kwargs)

        if params is None:
            params = {}
        if "page" in params:
            raise ValueError("Cannot autopage the request if the page param is specified.")
        else:
            params["page"] = 1

        # TODO: Test this.

        logger.debug(
            'Making autopage request to ("%s", "%s") with max concurrent requests at %s.',
            method,
            route,
            max_concurrent_requests,
        )
        initial_response = await self.request(
            method, route, datasource=datasource, auth=auth, params=params, headers=headers
        )
        total_pages = initial_response.headers.get("x-pages")
        ret = {1: initial_response}
        if total_pages is not None:
            total_pages = int(total_pages)
            async with asyncio.TaskGroup() as tg:
                tasks = []
                for i in range(2, total_pages + 1):
                    task_param = params.copy()
                    task_param["page"] = i
                    tasks.append(
                        tg.create_task(
                            concurrent_request(
                                method,
                                route,
                                datasource=datasource,
                                auth=auth,
                                params=task_param,
                                headers=headers,
                            )
                        )
                    )

            for task in tasks:
                result: ESIResponse = task.result()
                ret[result.page] = result

        return ret

    # --- Market

    async def get_markets_region_history(
        self,
        region_id: int,
        type_id: int,
        *,
        language: Language | None = None,
        datasource: Datasource | None = None,
    ) -> ESIResponse:
        params = {}
        if language:
            params["language"] = language.value

        return await self.request(
            "GET",
            f"/v1/markets/{region_id}/history",
            params={"type_id": str(type_id)},
            datasource=datasource,
        )

    async def get_markets_region_orders(
        self,
        region_id: int,
        order_type: MarketOrderType,
        *,
        type_id: int | None = None,
        page: int = 1,
        autopage: bool = True,
        language: Language | None = None,
        datasource: Datasource | None = None,
    ) -> dict[int, ESIResponse] | ESIResponse:
        params = {"order_type": order_type.value}
        if type_id is not None:
            params["type_id"] = type_id
        if language:
            params["language"] = language.value

        if autopage:
            return await self.autopage_request(
                "GET", f"/v1/markets/{region_id}/orders", datasource=datasource, params=params
            )
        else:
            params["page"] = page
            return await self.request(
                "GET", f"/v1/markets/{region_id}/orders", datasource=datasource, params=params
            )

    # --- Planetary Interaction

    async def get_character_planets(
        self, character_id, access_token: EVEAccessToken | str, *, datasource: DatasourceType = None
    ) -> ESIResponse:
        if isinstance(access_token, EVEAccessToken):
            access_token = access_token.token

        return await self.request(
            "GET",
            f"/v1/characters/{character_id}/planets/",
            datasource=datasource,
            auth=f"Bearer {access_token}",
        )

    async def get_character_planet(
        self,
        character_id: int,
        planet_id: int,
        access_token: EVEAccessToken | str,
        *,
        datasource: DatasourceType = None,
    ):
        if isinstance(access_token, EVEAccessToken):
            access_token = access_token.token

        return await self.request(
            "GET",
            f"/v3/characters/{character_id}/planets/{planet_id}",
            datasource=datasource,
            auth=f"Bearer {access_token}"
        )

    # --- Status

    async def get_status(self, *, datasource: DatasourceType = None) -> ESIResponse:
        return await self.request("GET", "/v2/status/", datasource=datasource)

    # --- Universe

    async def get_universe_constellation_info(
        self,
        constellation_id: int,
        *,
        language: Language | None = None,
        datasource: Datasource | None = None,
    ):
        params = {}
        if language:
            params["language"] = language.value

        return await self.request(
            "GET", f"/v1/universe/constellations/{constellation_id}", params=params, datasource=datasource
        )

    async def post_universe_ids_resolve(
        self,
        names: list[str],
        *,
        language: Language | None = None,
        datasource: Datasource | None = None,
    ):
        params = {}
        if language:
            params["language"] = language.value

        return await self.request(
            "POST", f"/v1/universe/ids/", json=names, params=params, datasource=datasource
        )

    async def get_universe_region_info(
        self,
        region_id: int,
        *,
        language: Language | None = None,
        datasource: Datasource | None = None,
    ):
        params = {}
        if language:
            params["language"] = language.value

        return await self.request(
            "GET", f"/v1/universe/regions/{region_id}", params=params, datasource=datasource
        )

    async def get_universe_solarsystem_info(
        self,
        solarsystem_id: int,
        *,
        language: Language | None = None,
        datasource: Datasource | None = None,
    ):
        params = {}
        if language:
            params["language"] = language.value
        return await self.request(
            "GET", f"/v4/universe/systems/{solarsystem_id}/", params=params, datasource=datasource
        )

    async def get_universe_type_info(
        self,
        type_id: int,
        *,
        language: Language | None = None,
        datasource: Datasource | None = None,
    ):
        params = {}
        if language:
            params["language"] = language.value

        return await self.request(
            "GET", f"/v3/universe/types/{type_id}/", params=params, datasource=datasource
        )

    # --- Misc, indirect ESI stuff.

    async def post_oauth_token(
        self,
        *,
        auth_code: str,
        grant_type: OAuthGrantType | str,
        client_id: str,
        client_secret: str,
    ) -> EVEOAuthTokenResponse:
        if isinstance(grant_type, Enum):
            grant_type = grant_type.value

        encoded_creds = base64.b64encode(bytes(f"{client_id}:{client_secret}", "utf-8")).decode("utf-8")
        headers = {
            "Authorization": f"Basic {encoded_creds}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Host": "login.eveonline.com",
        }
        data = {"grant_type": grant_type, "code": auth_code}
        # logger.debug("test \n\n%s\n\n%s\n\n%s\n\nend test", encoded_creds, headers, data)
        response = await self.request("POST", OAUTH_TOKEN_URL, data=data, headers=headers, base_url="")
        return await EVEOAuthTokenResponse.from_esi_response(response)

    async def get_access_token(
        self,
        refresh_token: str,
        client_id: str,
        client_secret: str,
        scopes: list[ESIScope | str] | None = None,
    ) -> EVEOAuthTokenResponse:
        data = {
            "grant_type": "refresh_token",
            # "refresh_token": urllib.parse.quote_plus(refresh_token),
            "refresh_token": refresh_token,
        }
        if scopes:
            scopes = [s.value if isinstance(s, ESIScope) else s for s in scopes]
            data["scope"] = " ".join(scopes)

        encoded_creds = base64.b64encode(bytes(f"{client_id}:{client_secret}", "utf-8")).decode("utf-8")
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Host": "login.eveonline.com",
            "Authorization": f"Basic {encoded_creds}",
        }
        response = await self.request(
            "POST",
            OAUTH_TOKEN_URL,
            data=data,
            headers=headers,
            base_url="",
        )
        return await EVEOAuthTokenResponse.from_esi_response(response)

    async def get_oauth_verify(self, access_token: str) -> ESIResponse:
        return await self.request("GET", OAUTH_VERIFY_URL, auth=f"Bearer {access_token}", base_url="")
