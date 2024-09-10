import asyncio
import base64
import datetime
import json
from enum import Enum
from logging import getLogger

from aiohttp import web
from aiohttp.typedefs import Handler, Middleware
from aiohttp.web import StreamResponse
from aiohttp.web_runner import TCPSite
import yarl

from .constants import OAUTH_RESPONSE_TEMPLATE
from .enums import OAuthResponseType, ESIScope

__all__ = (
    "BaseEndpoint",
    "BaseMiddleware",
    "create_oauth_url",
    "EVEOAuth2Endpoint",
)


BASE_OAUTH_URL = "https://login.eveonline.com/v2/oauth/authorize"


logger = getLogger(__name__)


class BaseEndpoint:
    middlewares: list[Middleware]
    site: TCPSite | None
    def __init__(self, middlewares: list[Middleware]) -> None:
        self.middlewares = middlewares
        self.site = None

    async def start(self, *, host: str = "0.0.0.0", port: int = 8080) -> web.TCPSite:
        app = web.Application(middlewares=self.middlewares)
        runner = web.AppRunner(app)
        await runner.setup()
        self.site = web.TCPSite(runner, host, port)
        await self.site.start()
        logger.info("%s listening on %s", self.__class__.__name__, self.site.name)
        return self.site

    def run(
        self,
        *,
        host: str = "0.0.0.0",
        port: int = 8080,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        loop = loop or asyncio.new_event_loop()
        task = loop.create_task(self.start(host=host, port=port))
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            logger.debug("KeyboardInterrupt encountered, stopping loop.")
            if task.done():
                site = task.result()
                loop.run_until_complete(site.stop())
            else:
                task.cancel()
            loop.run_until_complete(asyncio.sleep(0.25))


class BaseMiddleware:
    def __init__(self, method: str = "GET", route: str = "/endpoint/default") -> None:
        self._method: str = method
        self._route: str = route

    @property
    def method(self) -> str:
        return self._method

    @property
    def route(self) -> str:
        return self._route

    @property
    def middleware(self):
        @web.middleware
        async def route_middleware(request: web.Request, handler: Handler) -> StreamResponse:
            if request.path.startswith(self.route) and request.method == self.method:
                return await self.on_middleware_match(request, handler)
            else:
                logger.debug("Ignoring request %s %s", request.method, request.url)
                resp = await handler(request)
                return resp

        return route_middleware

    async def on_middleware_match(self, request: web.Request, handler: Handler) -> StreamResponse:
        raise NotImplementedError


class EVEOAuth2Endpoint(BaseMiddleware, BaseEndpoint):
    def __init__(self, route: str = "/endpoint/oauth2") -> None:
        BaseMiddleware.__init__(self, route=route)
        BaseEndpoint.__init__(self, [self.middleware])

    async def on_middleware_match(self, request: web.Request, handler: Handler) -> StreamResponse:
        if request.rel_url.query.get("code"):
            logger.debug("Query has code, executing on_oauth_endpoint and sending positive response.")
            # TODO: Should this made into a task or try/except so errors don't affect the response, or
            #  should erroring make a 50X error appear like it does currently?
            await self.on_oauth_endpoint(
                request.url.with_query(None).human_repr(),
                request.rel_url.query["code"],
                request.rel_url.query.get("state", None),
            )
            # TODO: Look into a better way of handling this, allowing custom responses? Maybe put them inside
            #  __init__ as kwargs?
            return web.Response(
                body=OAUTH_RESPONSE_TEMPLATE.format(
                    "OAuth Accepted.", "<h1>👍 OAuth Received 👍</h1><h1>Close Whenever</h1>"
                ),
                content_type="text/html",
            )
        else:
            logger.debug("Query doesn't have code, sending negative response.")
            return web.Response(
                body=OAUTH_RESPONSE_TEMPLATE.format(
                    "OAuth Denied.", "<h1>👎 No Oauth 👎</h1><h1>Close Whenever</h1>"
                ),
                content_type="text/html",
            )

    async def on_oauth_endpoint(self, redirect_uri: str, code: str, state: str | None) -> None:
        logger.debug("%s %s, %s", redirect_uri, code, state)


def create_oauth_url(
    *,
    response_type: OAuthResponseType | str,
    redirect_url: str,
    client_id: str,
    scope: list[ESIScope | str],
    state: str,
) -> str:
    response_type = response_type.value if isinstance(response_type, Enum) else response_type
    scope = " ".join([s.value if isinstance(s, Enum) else s for s in scope])
    ret = yarl.URL(BASE_OAUTH_URL)
    ret = ret.with_query(
        {
            "response_type": response_type,
            "redirect_uri": redirect_url,
            "client_id": client_id,
            "scope": scope,
            "state": state,
        }
    )
    return str(ret)
