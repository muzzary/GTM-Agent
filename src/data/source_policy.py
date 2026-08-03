import socket
from collections.abc import Callable
from dataclasses import dataclass
from ipaddress import ip_address
from urllib.parse import SplitResult, urlsplit, urlunsplit

Resolver = Callable[[str], tuple[str, ...]]


class SourcePolicyError(ValueError):
    pass


@dataclass(frozen=True)
class SourcePolicy:
    policy_version: str
    allowed_hosts: frozenset[str]
    allowed_path_prefixes: tuple[str, ...]
    allowed_content_types: frozenset[str]
    robots_required: bool
    max_redirects: int = 0
    max_response_bytes: int = 1_048_576
    minimum_request_interval_seconds: float = 1.0
    cache_ttl_seconds: int = 86_400


@dataclass(frozen=True)
class ValidatedUrl:
    url: str
    host: str
    path: str


def system_resolver(host: str) -> tuple[str, ...]:
    addresses = {
        item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    }
    return tuple(sorted(addresses))


def validate_url(
    raw_url: str,
    policy: SourcePolicy,
    resolver: Resolver,
) -> ValidatedUrl:
    try:
        parsed = urlsplit(raw_url)
        host = _normalized_host(parsed)
    except (UnicodeError, ValueError) as error:
        raise SourcePolicyError("invalid URL") from error
    if parsed.scheme.lower() != "https":
        raise SourcePolicyError("source URL must use HTTPS")
    if parsed.username is not None or parsed.password is not None:
        raise SourcePolicyError("source URL cannot include credentials")
    if parsed.fragment:
        raise SourcePolicyError("source URL cannot include a fragment")
    if parsed.port not in {None, 443}:
        raise SourcePolicyError("source URL cannot use a custom port")
    try:
        ip_address(host)
    except ValueError:
        pass
    else:
        raise SourcePolicyError("IP-literal source hosts are not allowed")
    if host not in policy.allowed_hosts:
        raise SourcePolicyError("source host is not admitted by policy")
    path = parsed.path or "/"
    if not any(path.startswith(prefix) for prefix in policy.allowed_path_prefixes):
        raise SourcePolicyError("source path is not admitted by policy")
    try:
        addresses = resolver(host)
    except OSError as error:
        raise SourcePolicyError("source host could not be resolved") from error
    if not addresses:
        raise SourcePolicyError("source host could not be resolved")
    try:
        public = all(ip_address(address).is_global for address in addresses)
    except ValueError as error:
        raise SourcePolicyError("resolver returned an invalid address") from error
    if not public:
        raise SourcePolicyError("source host must resolve only to a public address")
    canonical = SplitResult("https", host, path, parsed.query, "")
    return ValidatedUrl(url=urlunsplit(canonical), host=host, path=path)


def _normalized_host(parsed: SplitResult) -> str:
    if parsed.hostname is None:
        raise ValueError("source URL requires a host")
    return parsed.hostname.rstrip(".").lower().encode("idna").decode("ascii")
