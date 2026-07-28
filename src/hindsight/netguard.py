"""Validate outbound DataHub endpoints before the SDK is handed a URL.

The console takes a DataHub server address from a form field and passes it to the
metadata SDK. Unvalidated, that is a server-side request forgery surface: an
operator who can reach the console can make the host fetch `file:///etc/passwd`,
or - the canonical cloud attack - the instance metadata service at
169.254.169.254, which returns credentials.

Guidance followed (OWASP SSRF prevention):

* allowlist the **scheme**; reject `file:`, `ftp:`, `gopher:`, `javascript:` and
  everything else at the parsing layer rather than denylisting known-bad ones;
* validate the **resolved address**, not the string, so encodings and DNS names
  pointing at internal ranges are caught;
* always block link-local (169.254.0.0/16, fd00:ec2::/32), because no legitimate
  metadata service lives there for this tool.

Loopback and private ranges are deliberately *allowed*: DataHub Core commonly
runs at `http://localhost:8080`, and a real deployment usually sits on a private
network. Blocking those would break the documented setup while doing nothing
about the actual risk, which is scheme abuse and metadata harvesting.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlsplit

ALLOWED_SCHEMES = frozenset({"http", "https"})

# Cloud instance-metadata services. Never a valid DataHub endpoint.
_METADATA_NETWORKS = (
    ipaddress.ip_network("169.254.0.0/16"),  # AWS/GCP/Azure IMDS, and link-local generally
    ipaddress.ip_network("fd00:ec2::/32"),  # AWS IMDSv2 over IPv6
)


class EndpointError(ValueError):
    """The supplied endpoint is not one this tool is willing to call."""


@dataclass(frozen=True)
class Endpoint:
    url: str
    host: str
    port: int | None
    resolved: tuple[str, ...]


def validate_endpoint(url: str, *, resolve: bool = True) -> Endpoint:
    """Return a validated endpoint, or raise :class:`EndpointError`."""
    if not url or not url.strip():
        raise EndpointError("No DataHub server address was supplied.")

    candidate = url.strip()
    parts = urlsplit(candidate)

    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        raise EndpointError(
            f"Unsupported scheme {parts.scheme or '(none)'!r}. "
            "Only http and https addresses are allowed."
        )
    if not parts.hostname:
        raise EndpointError("The address has no host.")

    try:
        port = parts.port
    except ValueError as error:  # out-of-range port
        raise EndpointError(f"Invalid port in {candidate!r}.") from error

    resolved: tuple[str, ...] = ()
    if resolve:
        resolved = _resolve(parts.hostname)
        for address in resolved:
            ip = ipaddress.ip_address(address)
            if any(ip in network for network in _METADATA_NETWORKS):
                raise EndpointError(
                    f"{parts.hostname} resolves to {address}, a link-local or cloud "
                    "metadata address. Refusing to call it."
                )

    return Endpoint(url=candidate, host=parts.hostname, port=port, resolved=resolved)


def _resolve(hostname: str) -> tuple[str, ...]:
    """Resolve a hostname to every address it points at.

    A name is checked after resolution, not before, so `metadata.example.com`
    pointing at 169.254.169.254 is caught. Resolution failure is not fatal - the
    call will fail on its own, and refusing to render a page because DNS is down
    would be worse than letting the request error.
    """
    try:
        infos = socket.getaddrinfo(hostname, None)
    except (socket.gaierror, UnicodeError, OSError):
        return ()
    return tuple(sorted({info[4][0] for info in infos}))
