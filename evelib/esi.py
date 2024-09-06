import asyncio
from datetime import datetime
from datetime import timezone
from logging import getLogger
from typing import Literal, Iterable

import aiohttp

from . import errors
from . import utils
from .constants import USER_AGENT
from .enums import Datasource, Language, MarketOrderType


__all__ = (
    "EVEESI",
    "ESIResponse",
)


logger = getLogger(__name__)


BASE_URL = "https://esi.evetech.net"

# USER_AGENT_BASE = "PyEveLib (https://github.com/alentoghostflame/pyevelib) Python/{0[0]}.{0[1]} aiohttp/{1}"
# USER_AGENT = USER_AGENT_BASE.format(sys.version_info, aiohttp.__version__)

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
        self.requested: datetime | None = None
        """When the data was requested, according to the EVE server."""
        self.expires: datetime | None = None
        """When the data expires and can/should be fetched again."""
        self.last_modified: datetime | None = None
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
        json: dict | list | None = None,
        datasource: DatasourceType | None = None,
        auth: str | None = None,
        params: dict[str, str] = None,
        headers: dict[str, str] = None,
    ) -> ESIResponse:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

        params = self._make_params(params or {}, datasource=datasource)
        headers = self._make_headers(headers or {}, auth=auth)

        cache_key = (method, route, str(params), str(headers))

        if self._use_internal_cache:
            if cached_response := self._cache.get(cache_key):
                if (
                    cached_response.expires is not None
                    and datetime.now(timezone.utc) < cached_response.expires
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
                method=method, url=BASE_URL + route, json=json, params=params, headers=headers
            ) as response:
                await self._error_rate_limit.update(response)

                ret = None  # TODO: This is a patch, remove this later.

                if response.status >= 400:
                    match response.status:
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

    # --- Status

    async def get_status(self, datasource: DatasourceType = None) -> ESIResponse:
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
        names: Iterable[str],
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
