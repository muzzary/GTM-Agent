import json
import re
from collections.abc import Sequence
from urllib.parse import urlencode, urlsplit

from src.data.http_collector import ControlledHttpCollector, ResearchCollectionError
from src.data.source_policy import SourcePolicy
from src.research.discovery import CandidateSuggestion, SourceObservation
from src.schemas.campaign import ICPProfile
from src.schemas.research import SourceCategory

_EXCLUDED_CANDIDATE_HOSTS = {
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "twitter.com",
    "x.com",
    "youtube.com",
}
_PAGE_CATEGORIES = (
    ("about", 0),
    ("company", 0),
    ("product", 1),
    ("solution", 1),
    ("service", 1),
    ("project", 2),
    ("case-stud", 2),
    ("news", 3),
    ("press", 3),
)


class MarketSeedDiscoveryProvider:
    name = "market_seed"

    def __init__(self, collector: ControlledHttpCollector) -> None:
        self._collector = collector

    def discover(
        self,
        icp: ICPProfile,
        seed_urls: Sequence[str],
    ) -> tuple[CandidateSuggestion, ...]:
        suggestions: list[CandidateSuggestion] = []
        seen_hosts: set[str] = set()
        for seed_url in seed_urls[:10]:
            seed_host = _host(seed_url)
            policy = website_policy(
                seed_host,
                policy_version="market-seed-v1",
            )
            document = self._collector.collect(seed_url, policy)
            observation = SourceObservation.from_document(
                document,
                provider="market_seed",
                publisher=seed_host,
                source_category=SourceCategory.APPROVED_MARKET_SOURCE,
                policy_version=policy.policy_version,
                license_basis="public_excerpt",
            )
            for link in document.links:
                if urlsplit(link).scheme != "https":
                    continue
                host = _host(link)
                registrable_hint = _without_www(host)
                if (
                    not host
                    or host == seed_host
                    or registrable_hint in _EXCLUDED_CANDIDATE_HOSTS
                    or host in seen_hosts
                ):
                    continue
                seen_hosts.add(host)
                suggestions.append(
                    CandidateSuggestion(
                        company=_company_from_host(host),
                        industry=icp.industries[0],
                        official_url=f"https://{host}/",
                        provider="market_seed",
                        observations=(observation,),
                    )
                )
                if len(suggestions) == 20:
                    return tuple(suggestions)
        return tuple(suggestions)


class WebsiteCandidateExpander:
    def __init__(self, collector: ControlledHttpCollector) -> None:
        self._collector = collector

    def expand(self, suggestion: CandidateSuggestion) -> CandidateSuggestion:
        host = _host(suggestion.official_url)
        policy = website_policy(
            host,
            policy_version="official-website-v1",
        )
        try:
            homepage = self._collector.collect(suggestion.official_url, policy)
        except ResearchCollectionError:
            return suggestion
        observations = list(suggestion.observations)
        observations.append(self._observation(homepage, suggestion, policy))
        selected = self._select_links(homepage.links, policy.allowed_hosts)[:2]
        for link in selected:
            try:
                document = self._collector.collect(link, policy)
            except ResearchCollectionError:
                continue
            observations.append(self._observation(document, suggestion, policy))
        providers = tuple(
            dict.fromkeys((suggestion.provider + "+official_site").split("+"))
        )
        return CandidateSuggestion(
            company=suggestion.company,
            industry=suggestion.industry,
            official_url=suggestion.official_url,
            provider="+".join(providers),
            observations=tuple(observations),
            source_entity_id=suggestion.source_entity_id,
        )

    @staticmethod
    def _select_links(
        links: Sequence[str], allowed_hosts: frozenset[str]
    ) -> tuple[str, ...]:
        ranked: list[tuple[int, str]] = []
        for link in links:
            parsed = urlsplit(link)
            host = (parsed.hostname or "").lower()
            if parsed.scheme != "https" or host not in allowed_hosts:
                continue
            lowered = (parsed.path + " " + parsed.query).casefold()
            priorities = [rank for term, rank in _PAGE_CATEGORIES if term in lowered]
            if priorities:
                ranked.append((min(priorities), link))
        ordered = sorted(set(ranked), key=lambda item: (item[0], item[1]))
        about = next((link for rank, link in ordered if rank == 0), None)
        detail = next((link for rank, link in ordered if rank > 0), None)
        selected = tuple(link for link in (about, detail) if link is not None)
        if len(selected) < 2:
            selected += tuple(link for _, link in ordered if link not in selected)[
                : 2 - len(selected)
            ]
        return selected

    @staticmethod
    def _observation(document, suggestion, policy) -> SourceObservation:
        return SourceObservation.from_document(
            document,
            provider="official_site",
            publisher=suggestion.company,
            source_category=SourceCategory.OFFICIAL_WEBSITE,
            policy_version=policy.policy_version,
            license_basis="public_excerpt",
        )


class WikidataDiscoveryProvider:
    name = "wikidata"

    _base_url = "https://www.wikidata.org/w/api.php"
    _query_url = "https://query.wikidata.org/sparql"

    def __init__(self, collector: ControlledHttpCollector) -> None:
        self._collector = collector
        self._search_policy = SourcePolicy(
            policy_version="wikidata-v1",
            allowed_hosts=frozenset({"www.wikidata.org"}),
            allowed_path_prefixes=("/w/api.php",),
            allowed_content_types=frozenset({"application/json"}),
            robots_required=False,
            max_redirects=0,
        )
        self._query_policy = SourcePolicy(
            policy_version="wikidata-query-v1",
            allowed_hosts=frozenset({"query.wikidata.org"}),
            allowed_path_prefixes=("/sparql",),
            allowed_content_types=frozenset(
                {"application/json", "application/sparql-results+json"}
            ),
            robots_required=False,
            max_redirects=0,
        )

    @classmethod
    def search_url(cls, industry: str) -> str:
        query = urlencode(
            {
                "action": "wbsearchentities",
                "format": "json",
                "language": "en",
                "limit": "20",
                "search": industry,
                "type": "item",
            }
        )
        return f"{cls._base_url}?{query}"

    @classmethod
    def company_query_url(cls, industry_ids: Sequence[str]) -> str:
        values = " ".join(f"wd:{item}" for item in industry_ids)
        sparql = f"""
SELECT ?company ?companyLabel ?website ?industryLabel WHERE {{
  VALUES ?industry {{ {values} }}
  ?company wdt:P452 ?industry;
           wdt:P856 ?website;
           wdt:P31/wdt:P279* wd:Q4830453.
  FILTER(STRSTARTS(STR(?website), "https://"))
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
LIMIT 20
""".strip()
        return f"{cls._query_url}?{urlencode({'format': 'json', 'query': sparql})}"

    def discover(
        self,
        icp: ICPProfile,
        _seed_urls: Sequence[str],
    ) -> tuple[CandidateSuggestion, ...]:
        suggestions: list[CandidateSuggestion] = []
        seen_entities: set[str] = set()
        for industry in icp.industries[:3]:
            search_document = self._collector.collect(
                self.search_url(industry), self._search_policy
            )
            search_payload = _json_object(search_document.text)
            entity_ids = tuple(
                item["id"]
                for item in search_payload.get("search", [])
                if isinstance(item, dict)
                and isinstance(item.get("id"), str)
                and item["id"].startswith("Q")
                and item["id"] not in seen_entities
            )[:3]
            if not entity_ids:
                continue
            query_document = self._collector.collect(
                self.company_query_url(entity_ids), self._query_policy
            )
            results = _json_object(query_document.text).get("results", {})
            bindings = results.get("bindings", []) if isinstance(results, dict) else []
            if not isinstance(bindings, list):
                continue
            for binding in bindings:
                if not isinstance(binding, dict):
                    continue
                entity_uri = _binding_value(binding, "company")
                company = _binding_value(binding, "companyLabel")
                official_url = _binding_value(binding, "website")
                industry_label = _binding_value(binding, "industryLabel")
                match = re.fullmatch(
                    r"https?://www\.wikidata\.org/entity/(Q[1-9][0-9]*)",
                    entity_uri,
                )
                if (
                    match is None
                    or not company
                    or not official_url.startswith("https://")
                ):
                    continue
                entity_id = match.group(1)
                if entity_id in seen_entities:
                    continue
                seen_entities.add(entity_id)
                citation_url = f"https://www.wikidata.org/wiki/{entity_id}"
                observation = SourceObservation(
                    provider="wikidata",
                    publisher="Wikidata",
                    source_category=SourceCategory.STRUCTURED_PUBLIC,
                    title=f"Wikidata entity {entity_id}: {company}",
                    url=citation_url,
                    retrieval_url=query_document.canonical_url,
                    text=f"{company}. Industry: {industry_label}.",
                    body_sha256=query_document.body_sha256,
                    policy_version=self._query_policy.policy_version,
                    license_basis="CC0 structured data; excerpt only",
                    fetched_at=query_document.fetched_at,
                    observed_at=query_document.observed_at,
                    cache_hit=query_document.cache_hit,
                )
                suggestions.append(
                    CandidateSuggestion(
                        company=company,
                        industry=industry,
                        official_url=official_url,
                        provider="wikidata",
                        observations=(observation,),
                        source_entity_id=entity_id,
                    )
                )
                if len(suggestions) == 20:
                    return tuple(suggestions)
        return tuple(suggestions)


def website_policy(
    host: str,
    *,
    policy_version: str,
) -> SourcePolicy:
    aliases = {host}
    if host.startswith("www."):
        aliases.add(host.removeprefix("www."))
    else:
        aliases.add(f"www.{host}")
    return SourcePolicy(
        policy_version=policy_version,
        allowed_hosts=frozenset(aliases),
        allowed_path_prefixes=("/",),
        allowed_content_types=frozenset({"text/html", "text/plain"}),
        robots_required=True,
        max_redirects=2,
    )


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").rstrip(".").lower()


def _without_www(host: str) -> str:
    return host.removeprefix("www.")


def _company_from_host(host: str) -> str:
    label = _without_www(host).split(".", 1)[0]
    return label.replace("-", " ").replace("_", " ").title()


def _json_object(text: str) -> dict:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as error:
        raise ResearchCollectionError("provider_invalid_json") from error
    if not isinstance(value, dict) or value.get("error") is not None:
        raise ResearchCollectionError("provider_error")
    return value


def _binding_value(binding: dict, key: str) -> str:
    value = binding.get(key)
    if not isinstance(value, dict) or not isinstance(value.get("value"), str):
        return ""
    return value["value"]
