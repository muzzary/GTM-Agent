# Phase 4 Specification: Multi-Source Prospect Discovery and Research

**Status:** Externally approved; awaiting user approval

## Objective

Build a bounded public-research pipeline that can:

1. discover prospect companies from multiple permitted market sources;
2. inspect candidate official websites to improve ICP ranking;
3. let the user select a prospect;
4. research that prospect's public website, products, projects, initiatives,
   and relevant market signals; and
5. preserve citations, uncertainty, conflicts, and unknowns for later
   positioning and outreach.

Wikipedia/Wikidata is one structured discovery seed, not the whole research
surface. The MVP is broad-source capable but does not claim exhaustive internet
coverage or unrestricted autonomous crawling.

Phase 4 succeeds when fixture and approved live runs produce evidence-backed
ranked prospects, a selected live prospect receives bounded deep research, and
positioning remains blocked until that research is complete.

## Corrected product intent

- The agent explores sources relevant to the submitted market and ICP, rather
  than relying on one preselected company or scenario.
- Target-company websites are first-class sources. The agent should inspect
  what a prospect does, its products/services, public projects, initiatives,
  newsroom material, and other useful public signals.
- Public market pages, association directories, registries, reports, and
  user-supplied seed pages may participate when their source policy permits it.
- No login-gated, paywalled, private, CAPTCHA-protected, or access-controlled
  source is bypassed.
- The system is a decision-support research agent, not a personal-data
  harvester, unrestricted crawler, or autonomous outreach sender.

## Decisions proposed for approval

1. **Multi-source architecture:** provider capabilities are separated into
   seed discovery, candidate expansion, and selected-prospect research.
2. **Initial live providers:**
   - Wikidata/MediaWiki for structured company and industry seeds;
   - user-supplied, source-policy-approved public market seed URLs;
   - controlled research of validated official company websites.
3. **Later provider expansion:** public registry, tender, report, news, and
   industry-directory adapters use the same contracts but are enabled only
   after a domain-specific policy and parser are configured and tested.
4. **No paid search dependency:** Phase 4 does not require Google, Bing, or a
   paid prospecting API. Coverage is measured and reported, never described as
   the whole web.
5. **HTTP dependency:** move the already locked `httpx2>=2.9.1` package from
   development to runtime dependencies. This adds no new package.
6. **Local cache:** use standard-library SQLite at the ignored path
   `data/research-cache.sqlite3`. This is a response/evidence cache, not durable
   campaign storage.
7. **One-worker MVP:** campaigns, active-run guards, and host limiters are
   process-local. The supported Phase 4 runtime uses one Uvicorn worker.

## Source categories and provider registry

Every provider declares capabilities and a versioned policy before use.

| Category | Phase 4 behavior | Examples |
| --- | --- | --- |
| Structured public API | Discover and corroborate organizations | Wikidata/MediaWiki |
| Official company domain | Shallow candidate expansion and deep research | Homepage, about, products, projects, newsroom, documentation |
| Approved market seed | Discover outbound candidate domains and market context | Public association/directory/market page supplied by user |
| Configured public registry/report | Adapter-ready; disabled until explicitly configured | Registries, filings, tenders, public reports |
| General news/search | Adapter-ready; not scraped generically in MVP | Approved public APIs or domain-specific feeds later |

`ResearchProvider` exposes only the capabilities it implements:

```text
discover(icp, seed_sources) -> candidate suggestions
expand_candidate(candidate) -> shallow company evidence
research_prospect(candidate) -> deep research evidence
```

The workflow routes by capability. Retrieved text can never select a provider,
construct a destination, or change source policy.

## Three-stage research workflow

### Stage 1: market discovery

Inputs are the approved ICP plus up to ten optional public market seed URLs.

Wikidata maps submitted industries to structured items and retrieves companies
with supporting `industry (P452)` and organization-class statements. User seed
pages may contribute candidate official-domain links when the page and link
both pass source policy. Candidate URLs from source text are suggestions only;
they are never fetched until independently normalized, validated, and admitted
to the official-domain policy.

Output: up to twenty deduplicated candidate suggestions with discovery
evidence, source diversity, unknown ICP fields, and uncertainty.

### Stage 2: shallow candidate expansion and ranking

For at most ten candidates, inspect no more than three pages on the validated
official domain:

- homepage;
- one about/company page; and
- one highest-priority products, solutions, projects, or newsroom page.

Page choice comes from same-domain links or sitemap entries whose normalized
URL/title contains configured category terms. It is deterministic and does not
follow instructions found in page text.

Output: ranked candidates with separate discovery score, evidence quality,
research completeness, uncertainty, and evidence-supported factors. The user
then selects one prospect.

### Stage 3: selected-prospect deep research

The selected prospect receives a separate bounded run. It may inspect up to
twelve pages and three approved source hosts:

- official homepage and about/company pages;
- products, services, solutions, projects, case studies, or portfolio pages;
- public documentation or technical pages;
- newsroom, press release, blog, partnership, launch, and initiative pages;
- public careers pages only for aggregate operational signals, never personal
  contact harvesting;
- configured public registry, tender, report, or market sources when enabled.

The run produces an immutable `ProspectResearchProfile` containing:

- what the company publicly says it does;
- products and services;
- projects, initiatives, launches, partnerships, and operational signals;
- evidence potentially relevant to the submitted ICP and later positioning;
- conflicting evidence;
- unknown required fields; and
- research completeness and quality.

The profile stores evidence excerpts, not unsupported summaries. Deterministic
page classification and term matching may label evidence categories; semantic
synthesis belongs to the later model/evaluation stage and must cite these IDs.

## Source-policy and access controls

### Admission policy

Every source has a `SourcePolicyRecord` with:

- exact normalized host and allowed path prefixes;
- source category and provider;
- admission basis (`configured`, `user_seed`, or `structured_official_url`);
- allowed methods and content types;
- robots/access-policy status;
- license/terms basis and excerpt-only flag;
- rate, timeout, byte, page, depth, and cache limits;
- policy version and review timestamp.

Wikidata has committed policy configuration. Dynamic official domains are
admitted only from a validated structured official-website statement or an
explicit user seed and still require all security/access checks. An unclear or
prohibited source fails closed and remains visible as a denied attempt.

### URL, DNS, redirect, and transport controls

- HTTPS only; no credentials, fragments, IP-literal hosts, non-443 ports, or
  malformed internationalized hostnames.
- Reject localhost and every non-global IPv4/IPv6 destination, including
  private, loopback, link-local, reserved, multicast, and metadata ranges.
- Resolve and validate every address before cache access and each request.
- Disable ambient proxies and credentials with `trust_env=False`.
- Keep TLS certificate verification enabled.
- Follow at most two redirects. Every redirect target is normalized and fully
  revalidated; cross-domain redirects require a pre-admitted exact host.
- Construct Wikidata citation URLs locally from validated entity IDs. Never
  fetch a response-supplied URL without normal source admission.
- Use one connection per host, explicit connect/read/write/pool timeouts, and a
  process-wide serial per-host limiter.

This is bounded egress control, not proof against every DNS-rebinding race.
Preflight resolution does not cryptographically bind the HTTP client's later
socket. The limitation is documented and no test overclaims otherwise.

### Robots, access, and content rules

- Fetch and evaluate `/robots.txt` for HTML sites with the project User-Agent.
- Respect `Disallow`, `Crawl-delay`, and request-rate directives where parsed.
- Cache robots rules for no more than 24 hours.
- A robots 4xx response means unavailable rules; a 5xx or network failure
  fails closed for that host.
- Robots permission is not legal authorization. Explicit terms/access-policy
  denial still blocks collection.
- Never bypass logins, paywalls, CAPTCHAs, consent barriers, or bot blocks.
- Accept bounded JSON from configured APIs and `text/html`/`text/plain` from
  websites. Record PDF links but defer PDF extraction until separately scoped.
- Do not execute JavaScript, submit forms, accept cookies for gated content, or
  download executable/media/archive files.
- Stream responses and cap both transfer and decoded content at 1 MiB.
- Store only bounded excerpts needed for evidence. Do not redistribute full
  pages whose terms/license do not permit it.

### Privacy rules

The collector discards email addresses, phone numbers, personal social links,
and named-person contact details unless a later explicitly approved use case
requires them. Aggregate company facts, public roles/team names, and public
company initiatives are in scope. Unnecessary personal data is not persisted,
ranked, or shown.

## Collection, parsing, and cache

`ControlledHttpCollector` owns network policy and is independent of ranking.
Resolver, transport, cache, clocks, and wait functions are injected in tests.

- Use a meaningful User-Agent built from `GTM_RESEARCH_CONTACT`; live research
  fails closed when it is missing.
- Serialize requests per host and wait at least one second, or longer when
  source policy/robots requires it.
- On HTTP 429/503, honor valid delta-seconds or HTTP-date `Retry-After` up to 30
  seconds; otherwise wait five seconds. Allow one total retry per request.
- Treat HTTP-200 API error envelopes as provider failures.
- Cache successful canonical responses for 24 hours by normalized URL, request
  variant, and policy version.
- Transactionally hash exact cached bytes. Corrupt, expired, mismatched, or
  stale entries are ignored, never served after source failure.
- Cache read failure falls back to network; cache write failure records a
  warning without discarding valid fetched evidence.
- HTML parsing uses the standard library, ignores script/style/noscript, never
  renders source HTML, extracts bounded visible text/title/links, and normalizes
  whitespace.

## Data contracts and provenance

### Evidence

Extend `EvidenceRecord` with:

- `source_kind`: `fixture`, `structured_public`, `official_website`, or
  `approved_market_source`;
- research run ID, provider, publisher, and source category;
- canonical citation URL and retrieval URL;
- source-policy version and license/terms basis;
- title, bounded excerpt, excerpt start/end offsets;
- evidence type: `fact`, `inference`, `conflict`, or `unknown`;
- original `fetched_at`, current `observed_at`, optional source-updated time;
- canonical evidence SHA-256 and collection status.

Evidence hash input is UTF-8 canonical JSON of the validated evidence
projection. Cache integrity separately hashes exact response bytes.

### Runs, factors, signals, and profiles

- `CollectionAttempt`: URL, host, provider, status, HTTP status, cache flag,
  timestamps, bounded error code, and no raw sensitive failure body.
- `ResearchRun`: unique request ID, campaign/ICP/prospect ownership, stage,
  provider set, status, attempt IDs, evidence IDs, prospect IDs, policy
  versions, warnings, failure code, and start/end timestamps.
- `RankingFactor`: ICP field, normalized target, observed value, evidence IDs,
  weight, match state (`matched`, `not_matched`, `unknown`), and explanation.
- `SupportedSignal`: category, text, evidence IDs, freshness, and uncertainty.
- `ProspectResearchProfile`: selected-prospect ownership, evidence/factor/
  signal IDs, coverage by required section, quality, completeness, conflicts,
  unknowns, and completion timestamp.

Live evidence, candidates, factors, signals, and profiles carry explicit run
ownership. Campaign validation requires same-run provenance. Failed runs have
no authorized output IDs. Superseded evidence remains for audit, but only the
latest successful discovery run's candidates are selectable.

## Ranking semantics

Do not combine unlike measurements into one opaque number.

- `discovery_score`: evidence-supported ICP priority from `0..1`.
- `evidence_quality`: source authority, freshness, corroboration, and conflict
  penalty from `0..1`.
- `research_completeness`: required-section coverage from `0..1`.
- `uncertainty`: low, medium, or high based on unknown/conflicting factors.

Initial discovery weights:

| Factor | Weight | Rule |
| --- | ---: | --- |
| Industry | 0.35 | Structured industry statement or corroborated official-site evidence |
| Company size | 0.20 | Only when a public source supports the submitted size band |
| Role/team relevance | 0.15 | Official pages show the relevant function/team context |
| Pain/signal relevance | 0.20 | Public project, initiative, job, launch, or operational evidence |
| Source diversity/freshness | 0.10 | Corroborated and current evidence, never mere source count |

Unsupported factors receive zero points and remain `unknown`; unknown is not
the same as `not_matched`. Every awarded factor references evidence. Ties sort
by evidence quality, completeness, normalized company name, then prospect ID.
The UI calls this priority ranking, not predicted revenue or conversion value.

## Workflow and API

Add states:

```text
awaiting_prospect_selection
        -> awaiting_prospect_research
        -> prospect_researched
        -> draft_ready (Phase 5+)
```

Selecting a prospect no longer authorizes draft generation. A completed,
provenance-valid deep-research profile is required first.

Commands:

```text
POST /campaigns/{campaign_id}/discovery-runs
{
  "request_id": "research-request-<uuid>",
  "market_seed_urls": ["https://approved-public-market-page.example/"]
}

POST /campaigns/{campaign_id}/prospects/{prospect_id}/select

POST /campaigns/{campaign_id}/prospects/{prospect_id}/research-runs
{ "request_id": "research-request-<uuid>" }

GET /campaigns/{campaign_id}/research-runs/{run_id}
```

Success responses return a typed outcome containing the run and updated
campaign. Persisted failures return stable RFC 9457-style problem details with
a public code and run ID. Missing server configuration returns 503 without a
run. Validation is 422; state, capacity, duplicate-active, and stale-apply
conflicts are 409; source/upstream failures are 502.

Request IDs enforce backend idempotency. One active run per campaign is
allowed. Network I/O never holds the campaign mutation lock. The workflow
snapshots state, performs the run, then rechecks state/version/capacity before
atomic apply. A duplicate active request cannot start another collector.

The deterministic fixture path gains a fixture deep-research stage so Phase 2
tests remain meaningful under the stronger gate. It remains clearly synthetic.

## Cardinality limits

- Up to 3 ICP industries per discovery run; larger requests fail explicitly.
- Up to 10 market seed URLs, 20 candidate suggestions, and 10 shallow-expanded
  candidates.
- Up to 3 shallow pages per candidate.
- One selected prospect and up to 12 deep-research pages across at most 3
  pre-admitted hosts.
- One link hop from an admitted seed page; no recursive general crawl.
- Up to 3 retained discovery/deep runs of each type per campaign.
- Up to 16 collection attempts per shallow run and 24 per deep run.
- Up to 64 evidence records in the current campaign contract; capacity is
  checked before apply and never silently truncates provenance.

## User interface

The Phase 3 completion screen becomes a research workspace:

1. Display fixture candidates as synthetic and allow optional market seed URLs.
2. Run live discovery and shallow expansion with a stable request ID.
3. Show candidate priority score, factor evidence, source categories, quality,
   completeness, uncertainty, conflicts, and unknowns.
4. Show citations as validated HTTPS links using normal React text rendering,
   `target="_blank"`, and `rel="noreferrer noopener"`.
5. Require explicit prospect selection.
6. Run and display selected-prospect deep research by section.
7. Show failed/denied sources and gaps without presenting them as facts.
8. Stop at `prospect_researched`; Phase 4 does not generate outreach.

## Configuration

Committed non-secret policies:

```text
configs/sources/wikidata.json
configs/sources/website-defaults.json
```

Local environment:

```text
GTM_RESEARCH_CONTACT=<email-or-public-contact-url>
GTM_RESEARCH_CACHE_PATH=data/research-cache.sqlite3
```

The contact identifies the client but is not copied into evidence/frontend
responses. Adding a registry/news/report domain requires a reviewed policy
record; it is configuration-driven, not a code-level universal allowlist.

## Implementation slices

### Slice 1: contracts, states, and source policy

Add provenance, run, ranking, signal, profile, problem-detail, and source-policy
contracts. Refactor the workflow's concrete fixture dependency into narrow
protocols. Add settings and committed policy files.

**Acceptance:** schema validation proves ownership, same-run support, failed-run
disjointness, explicit unknowns, state gates, and bounds.

### Slice 2: controlled collector, robots, parsing, and cache

Implement URL/DNS/redirect policy, HTTPX2 transport configuration, robots
handling, rate limiting, bounded HTML/JSON parsing, privacy filtering, hashing,
and SQLite caching using injected test boundaries.

**Acceptance:** fake-transport tests prove all stated allow/deny, retry, cache,
content, and privacy behavior without internet-dependent CI.

### Slice 3: discovery and shallow candidate expansion

Implement Wikidata structured discovery, approved market-seed link extraction,
official-domain admission, shallow page selection, deduplication, factors, and
priority ranking.

**Acceptance:** fixture and live-compatible fake runs produce deterministic
ranked candidates with multi-source provenance; unsupported claims get no
points.

### Slice 4: selection and deep prospect research

Implement selection gate, bounded selected-prospect website research,
sectioned profile, conflicts/unknowns, completeness, quality, and downstream
authorization barrier.

**Acceptance:** draft generation fails before completed research; supported
fixture research and live-compatible fake research reach
`prospect_researched` with complete provenance.

### Slice 5: frontend research workspace

Add typed defensive guards, market seed input, candidate evidence/ranking,
selection, deep-research views, citations, denied-source and failure handling,
loading/focus/keyboard behavior, and responsive styling.

**Acceptance:** malformed responses cannot render or authorize state; fixture
and live workflows are clearly distinguished and accessible.

### Slice 6: documentation and verification

Update README, environment template, directory map, phase log, and a Phase 4
manual runbook covering live sources, cache reuse, denial, selection, and deep
research.

## Automated verification

- Source/provider routing, capability enforcement, and source-diversity tests.
- HTTPS, credentials, IP literal, IPv4/IPv6 private ranges, mixed DNS,
  redirects, TLS, ambient proxy, MIME, transfer/decompression size, timeout,
  rate, retry, and API-envelope tests.
- Robots allow/deny, 4xx, 5xx, delay, cache, and explicit access-policy denial.
- Cache miss/hit/expiry, raw hash, evidence hash, policy version, corruption,
  lock/read/write failure, and original-fetch/current-observation timestamps.
- HTML title/text/link extraction, same-host hop limits, page-category
  selection, privacy filtering, malformed markup, and prompt-injection text.
- Candidate deduplication, source corroboration, deterministic tie-break,
  supported-factor arithmetic, unknown/not-match distinction, and conflicts.
- Deep-research required-section coverage, completeness/quality calculations,
  same-run citations, and incomplete-profile downstream rejection.
- Request idempotency, active-run conflict, stale apply, capacity, failed-run
  retrieval, atomicity, trace ordering, and multi-campaign lock isolation.
- Frontend response guards, seed validation, loading/duplicate submit, evidence,
  citations, ranking, selection, research gaps, failures, focus, and keyboard.
- All Phase 0-3 regression tests remain green after intentional workflow-gate
  updates are reflected in fixture tests and runbooks.

Full gates:

```powershell
uv run pytest -q
uv run ruff check .
uv lock --check
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run build
```

CI uses fake transports/resolvers. Public-source requests are manual acceptance
only.

## Manual acceptance

1. Configure a real `GTM_RESEARCH_CONTACT`.
2. Complete claim review and inspect synthetic fixture candidates.
3. Run discovery for one market, optionally adding an approved public market
   seed page.
4. Verify candidates include structured and official-site evidence where
   available, with honest gaps and denied attempts.
5. Inspect ranking factors, source quality/diversity, completeness, conflicts,
   timestamps, hashes, and citations.
6. Select one live prospect and run deep research.
7. Verify the profile shows what the company does, products/projects, public
   initiatives/signals, relevant evidence, conflicts, and unknowns.
8. Repeat with a new request ID and confirm cache reuse preserves original
   fetch time while recording current observation time.
9. Confirm draft generation is blocked before research and remains outside the
   Phase 4 UI after research.
10. Remove contact configuration or use a denied source and confirm explicit,
    non-destructive failure.

## Authoritative references

- [Wikimedia Action API etiquette](https://www.mediawiki.org/wiki/API%3AEtiquette/en)
- [Wikimedia API access policy](https://www.mediawiki.org/wiki/Wikimedia_APIs/Access_policy)
- [Wikimedia API rate limits](https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits)
- [Wikidata data access](https://www.wikidata.org/wiki/Help%3AData_access)
- [Wikibase structured search](https://www.mediawiki.org/wiki/Help%3AExtension%3AWikibaseCirrusSearch#haswbstatement)
- [Robots Exclusion Protocol, RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html)
- [OWASP SSRF guidance](https://owasp.org/www-community/attacks/Server_Side_Request_Forgery)
- [HTTPX2 timeouts](https://httpx2.pydantic.dev/advanced/timeouts/)
- [HTTPX2 environment handling](https://httpx2.pydantic.dev/environment_variables/)

## Explicit deferrals

- Exhaustive web search or claims of whole-internet coverage.
- Generic scraping of Google/Bing or bypassing search-provider terms.
- JavaScript/browser automation, login/paywall/CAPTCHA handling, and deep
  recursive crawling.
- PDF extraction, social-media crawling, personal contact enrichment, email
  verification, and CRM integration.
- Unconfigured registry/news/report providers and paid prospecting APIs.
- Distributed campaigns, background workers, cross-process rate limiting, and
  production-grade crawler infrastructure.
- Model-based semantic synthesis/ranking, outreach generation, and sending.
