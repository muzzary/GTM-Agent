from ipaddress import ip_address

import pytest

from src.data.source_policy import SourcePolicy, SourcePolicyError, validate_url


def public_resolver(_host: str) -> tuple[str, ...]:
    return ("93.184.216.34",)


def official_policy() -> SourcePolicy:
    return SourcePolicy(
        policy_version="website-v1",
        allowed_hosts=frozenset({"example.com", "www.example.com"}),
        allowed_path_prefixes=("/",),
        allowed_content_types=frozenset({"text/html", "text/plain"}),
        robots_required=True,
    )


def test_url_policy_accepts_only_pre_admitted_public_https_destinations() -> None:
    validated = validate_url(
        "https://example.com/about?source=market",
        official_policy(),
        public_resolver,
    )

    assert validated.host == "example.com"
    assert validated.url == "https://example.com/about?source=market"

    unsafe = (
        "http://example.com/about",
        "https://user:pass@example.com/about",
        "https://example.com:444/about",
        "https://example.com/about#team",
        "https://127.0.0.1/about",
        "https://other.example/about",
    )
    for url in unsafe:
        with pytest.raises(SourcePolicyError):
            validate_url(url, official_policy(), public_resolver)


@pytest.mark.parametrize(
    "address",
    ["127.0.0.1", "10.0.0.2", "169.254.169.254", "::1", "fc00::1"],
)
def test_url_policy_rejects_any_non_global_resolved_address(address: str) -> None:
    assert not ip_address(address).is_global

    with pytest.raises(SourcePolicyError, match="public address"):
        validate_url(
            "https://example.com/",
            official_policy(),
            lambda _host: ("93.184.216.34", address),
        )

