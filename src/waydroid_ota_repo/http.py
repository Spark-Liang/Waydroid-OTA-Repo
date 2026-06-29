import socket
from collections.abc import Callable

import httpx2

_LIMITS = httpx2.Limits(
    max_connections=200,
    max_keepalive_connections=40,
    keepalive_expiry=30.0,
)
_TIMEOUT = httpx2.Timeout(connect=5.0, read=30.0, write=10.0, pool=10.0)
_SOCKET_OPTIONS: list[tuple[int, int, int]] = [
    (socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
]
type ResponseHook = Callable[[httpx2.Response], None]


def create_client(*, response_hooks: list[ResponseHook] | None = None) -> httpx2.Client:
    transport = httpx2.HTTPTransport(
        http2=True,
        retries=3,
        limits=_LIMITS,
        socket_options=_SOCKET_OPTIONS,
    )
    event_hooks = {"response": response_hooks or []}
    return httpx2.Client(
        transport=transport,
        timeout=_TIMEOUT,
        follow_redirects=True,
        event_hooks=event_hooks,
    )
