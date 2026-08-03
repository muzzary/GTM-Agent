# Phase 4 Follow-up: Regional Fit and Research Usability

## Objective

Improve the accepted Phase 4 workflow before outreach baselining so users can
restrict prospect discovery to intended regions, collect a broader evidence
profile for a selected company, and understand the result without reading raw
technical excerpts.

The follow-up remains deterministic and evidence-first. It does not add model
inference, unrestricted crawling, inferred geography, or unsupported company
claims.

## Product and interface decisions

### Regional ICP eligibility

- Add `regions` to campaign ICP input and persisted ICP profiles as an additive
  list of normalized labels, with at most 12 entries.
- An empty list preserves the existing global-search behavior.
- When regions are present, a live candidate is eligible only when retained
  evidence explicitly supports at least one submitted region.
- Unknown geography and observed out-of-region geography are not eligible for
  the returned live prospect list. They are not silently treated as matches.
- Wikidata discovery resolves submitted labels and queries company country or
  headquarters location. Retained structured evidence names the observed
  region and supports the region eligibility factor.
- Approved market-seed candidates remain eligible only if their retained public
  evidence explicitly contains a submitted region label.
- Fixture candidates remain clearly synthetic and include the submitted region
  only to exercise the workflow; they are never presented as public evidence.

### Company feature coverage

- Keep the existing exact-host, HTTPS, public-DNS, robots, redirect, request,
  page-count, and content-size boundaries.
- Expand the selected-company link vocabulary for company, offerings,
  projects/customers, news/initiatives, and technical material.
- Use a bounded second pass over links found on successfully collected pages to
  fill still-unknown sections without exceeding twelve total pages.
- Treat failed pages, policy denials, JavaScript-only content, PDFs, and missing
  section evidence as limitations or `unknown`, never as negative facts.

### Plain-language report

- Add a typed, ordered finding for every required research section.
- Each finding has a familiar label, `found` or `unknown` status, a short
  deterministic summary, and same-run evidence IDs when found.
- The primary frontend report shows the short findings and limitations.
- Raw citations, exact retained excerpts, source category, and collection
  warnings remain available in an expandable audit section.

### English summary translation

- Preserve every retained source excerpt in its original language and hash it
  before translation.
- Add a typed translation boundary that receives bounded summary text plus an
  explicit source-language code and returns English text with provider/model
  provenance.
- English summaries must cite the unchanged original evidence IDs and declare
  whether they are original English, translated, or translation-unavailable.
- Translation failure leaves the original finding available and adds a visible
  limitation; it must not abort company research or fabricate an English claim.
- The recommended production adapter is the distilled 600M NLLB model in Colab,
  subject to explicit dependency/model approval and an evaluation set covering
  business terminology. A fake translator proves the local contract without
  adding model weights to the repository.

## API contracts

- `ICPInput.regions: list[str] = []`
- `ICPProfile.regions: tuple[str, ...] = ()`
- `ProspectCandidate.region: str | None`
- Region-scoped live prospects include a `region` ranking factor with matched
  evidence. The factor is an eligibility gate rather than score inflation.
- `ProspectResearchProfile.findings` contains one finding per required section.
- Findings expose `source_language`, `summary_language`, and translation status;
  translated text never replaces the original evidence excerpt.
- Existing fields remain present; this is an additive contract change.

## Commands

- Backend tests: `uv run pytest -q`
- Backend lint: `uv run ruff check .`
- Lock verification: `uv lock --check`
- Frontend tests: `npm.cmd test` from `frontend/`
- Frontend lint: `npm.cmd run lint` from `frontend/`
- Frontend typecheck: `npm.cmd run typecheck` from `frontend/`
- Frontend build: `npm.cmd run build` from `frontend/`

## Project structure

- `src/schemas/`: additive ICP, candidate, and research-finding contracts.
- `src/research/`: region-aware providers/ranking and bounded research report
  construction.
- `src/runtime/`: campaign and fixture propagation.
- `frontend/src/forms/`: region input normalization and validation.
- `frontend/src/components/`: regional fit and readable report presentation.
- `tests/` and `frontend/src/**/*.test.tsx`: contract, behavior, and regression
  coverage.
- `docs/`: specification, runbook, and phase-log updates.

## Code style

Use the repository's strict Pydantic boundaries and immutable tuples internally.
External evidence must resolve by ID rather than being copied into summaries.

```python
ResearchFinding(
    section="offerings",
    status="found",
    summary="Product or service information was found on the official site.",
    evidence_ids=("evidence-example1",),
)
```

## Testing strategy

- Write failing contract and behavior tests before each increment.
- Prove region normalization, backward-compatible empty regions, supported
  regional matches, and exclusion of unknown/out-of-region live candidates.
- Prove page discovery remains within the admitted host and twelve-page bound.
- Prove every finding is either evidence-backed or explicitly unknown.
- Prove the frontend renders plain findings first and raw provenance only when
  expanded.
- Run all backend and frontend regression gates before manual verification.

## Boundaries

### Always

- Cite region and company findings with same-run evidence.
- Preserve unknowns, source warnings, and raw provenance.
- Keep live collection bounded and SSRF-safe.

### Ask first

- Add a dependency, external provider, geocoding service, JavaScript browser,
  PDF extraction stack, or model-generated research summary.

### Never

- Infer region from a top-level domain, company name, language, or IP address.
- Treat missing content as proof that a company lacks a feature.
- Hide warnings or replace citations with unsupported prose.

## Ordered tasks

1. Add the regional ICP contract, fixture propagation, frontend form field, and
   boundary validation.
2. Add Wikidata region resolution, candidate region evidence, hard eligibility,
   and transparent ranking output.
3. Broaden bounded selected-company page discovery and preserve unknowns and
   per-page warnings.
4. Add evidence-backed research findings, the translation provider contract,
   and the plain-language frontend report with expandable technical provenance.
5. Add the approved NLLB Colab translation adapter and evaluate representative
   business-language examples without committing weights.
6. Run full verification, self-review, and the updated manual runbook.

## Success criteria

- A campaign with no regions behaves as before.
- A campaign with regions returns only live candidates with cited matching
  geography.
- Selected-company research reads no more than twelve admitted pages and
  increases useful section coverage without fabricating missing features.
- The report presents five familiar, short findings with unknowns and
  limitations clearly visible.
- Non-English findings either have a provenance-labelled English translation or
  an explicit translation-unavailable limitation while retaining original text.
- A reviewer can expand every found item to inspect its exact public evidence.

## Open questions deferred beyond this follow-up

- Whether to add a reviewed geographic ontology for aliases such as `US`,
  `United States`, `North America`, and `EMEA`.
- Whether JavaScript rendering or PDF extraction earns its additional security,
  dependency, and resource cost.
- Whether a later evaluated model may paraphrase retained evidence beyond
  faithful translation without weakening factuality.
