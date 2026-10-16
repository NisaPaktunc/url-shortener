"""Rate limiting with slowapi.

One shared limiter. Each limited endpoint names its limit with a function,
so the value is read from the settings when a request arrives. This lets
tests change a limit without reloading the app.

The counters live in the memory of the app process. With several app
processes, each one counts for itself.
"""

from fastapi import Request
from slowapi import Limiter

from app.config import settings


def client_ip(request: Request) -> str:
    """The key to count by: the IP address of the client.

    Without a proxy this is the address that connected to the app.

    Behind proxies (TRUSTED_PROXY_HOPS = how many), the connecting address is
    the proxy's. The client address is in the X-Forwarded-For header, but a
    client can send that header itself, and a proxy only ADDS its entry at the
    end. So the left side can be forged and cannot be trusted. We count from
    the right instead: with one proxy the last entry was written by that proxy,
    with two proxies it is the second to last, and so on.
    """
    direct = request.client.host if request.client else "unknown"
    hops = settings.trusted_proxy_hops
    if hops == 0:
        return direct
    entries = [
        part.strip()
        for header in request.headers.getlist("x-forwarded-for")
        for part in header.split(",")
        if part.strip()
    ]
    return entries[-hops] if len(entries) >= hops else direct


limiter = Limiter(key_func=client_ip, enabled=settings.rate_limit_enabled)


def login_limit() -> str:
    """The limit for POST /auth/login."""
    return settings.login_rate_limit


def create_link_limit() -> str:
    """The limit for POST /links."""
    return settings.create_link_rate_limit
