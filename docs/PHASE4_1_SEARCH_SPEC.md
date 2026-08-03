# Phase 4.1: Fast, Broad, and Recoverable Public Research

## Objective

Reduce prospect-discovery latency while increasing useful public-source
coverage. Discovery should return strong candidates quickly, explain partial
source failures accurately, and retain safe paths to verified company sites.

This increment improves collection and ranking. It does not generate outreach,
infer unsupported company facts, bypass access controls, or turn discovery into
an unrestricted crawler.

## Approved decisions

- Resolve each submitted industry and region to an exact Wikidata entity before
  querying companies. Similar search results are not accepted as equivalents.
- Replace the broad label-service query with a bounded query that filters and
  limits candidates before resolving display labels.
- Run independent discovery providers concurrently within a shared deadline.
- Add optional Brave Search discovery through the existing HTTP boundary. It is
  disabled unless a user supplies an API key through the environment.
- Add `trafilatura`, `rapidfuzz`, and `tldextract` as reviewed dependencies for
  focused extraction, candidate deduplication, and registrable-domain handling.
- Do not add Playwright now. JavaScript rendering remains a later, isolated
  fallback only if measured coverage proves it necessary.

## Performance contract

- Target time to first eligible candidates: at most 5 seconds under normal
  source conditions.
- Bound a complete discovery run to 15 seconds, excluding selected-prospect
  deep research.
- Limit each structured/search provider to 20 suggestions and shallow-expand
  only the ten highest-value unique company domains.
- Reuse long-lived HTTP clients and the existing persistent research cache.
- Performance unit tests verify query shape, concurrency, deadlines, and work
  bounds deterministically. Live-source timing is a manual benchmark because a
  public endpoint cannot provide a stable CI latency guarantee.

## Discovery pipeline

1. Normalize submitted ICP industries and regions.
2. Resolve exact structured entities and query only company IDs, official
   HTTPS sites, submitted industries, and submitted regions.
3. In parallel, query configured search providers and approved market seeds.
4. Normalize registrable domains, remove duplicates, and rank retained source
   observations before website expansion.
5. Shallow-expand only the best unique candidates. Deep research remains an
   explicit selected-prospect action.

## Redirect recovery

A cross-domain redirect may be admitted only when every hop remains HTTPS,
resolves exclusively to public addresses, stays within the redirect limit, and
the destination is supported by a company-identity signal. Accepted signals
are a structured official website, reciprocal/canonical site metadata, or an
explicit `Organization.sameAs` relationship. An ordinary cross-domain redirect
without identity evidence remains denied and visible as a warning.

Registrable-domain comparisons use the packaged public-suffix snapshot; they
must not trigger an uncontrolled network download at runtime.

## Focused company extraction

- Prefer `robots.txt`, sitemap URLs, navigation links, canonical metadata, and
  JSON-LD organization data over broad crawling.
- Rank pages for company, offerings, projects/customers, news/initiatives, and
  technical material before collection.
- Use `trafilatura` only on already-admitted, bounded HTML documents.
- Preserve original evidence, hashes, warnings, and unknown sections.
- Translate only bounded summaries; never replace original source evidence.

## Error semantics

- `no_candidates`: at least one discovery source completed successfully but no
  eligible candidate survived evidence and region rules.
- `source_timeout`: every usable source timed out before producing a result.
- `source_failure`: every usable source failed for non-timeout reasons.
- Partial failures remain warnings when another source returns candidates.

## Security and privacy boundaries

- Preserve HTTPS-only URLs, public-DNS validation, robots enforcement, content
  limits, request limits, and explicit redirect limits.
- Never send private product descriptions, user notes, credentials, or approved
  claims to a search provider. Queries contain only normalized public-market ICP
  terms and optional region terms.
- API keys are environment-only, redacted from logs, and never persisted in
  campaign artifacts.
- Search snippets are discovery hints, not sufficient evidence for claims.

## Verification

- Unit tests prove exact entity selection and the optimized SPARQL shape.
- Service tests prove providers overlap in time, deadlines are bounded, and
  source failures are not mislabeled as empty results.
- Provider tests prove optional search configuration and safe query contents.
- Redirect tests prove verified migrations succeed and unrelated redirects fail.
- Extraction tests prove page budgets, sitemap preference, readable output, and
  preservation of unknowns.
- Run backend tests, Ruff, lock verification, frontend tests, lint, typecheck,
  and build before manual review.

## Manual acceptance

- A representative regional logistics campaign returns live candidates without
  waiting on the previous broad Wikidata query.
- The UI distinguishes an empty market result from an unavailable source.
- Search without a Brave key still works through structured data and seeds.
- A verified company-domain migration is recoverable without weakening SSRF
  protection for arbitrary redirects.
- Selected-company research presents concise English findings and expandable
  original evidence.
