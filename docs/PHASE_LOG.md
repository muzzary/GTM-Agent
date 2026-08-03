# Phase Log

## Phase 0: Repository scaffold

**Status:** Approved

**Changed:**

- Added the repository instructions in `AGENTS.md`.
- Added the directory responsibilities map in `DIRECTORY_MAP.md`.
- Added a defensive Python/project `.gitignore`.
- Created the proposed source, test, experiment, data, results, docs, and
  configuration directories with `.gitkeep` placeholders.

**Verification:**

- Confirmed all 12 planned directories exist.
- Confirmed all 12 directories have a tracked placeholder.
- Confirmed `AGENTS.md` references `DIRECTORY_MAP.md`.
- Confirmed `DIRECTORY_MAP.md` references `PROJECT_SCOPE.md`.
- Confirmed representative secrets, local data, result files, and model
  artifacts are ignored by Git.
- No automated test suite exists yet because implementation has not started.

**Manual review needed:**

- Confirm the proposed directory boundaries and naming before implementation.
- Resolve the approval questions in `PROJECT_SCOPE.md` before adding runtime
  code or dependencies.

## Planning phase: implementation roadmap

**Status:** Superseded by the approved reusable-agent roadmap

**Changed:**

- Added `docs/IMPLEMENTATION_PLAN.md` with nine dependency-ordered phases.
- Listed candidate runtime, model, training, serving, and development
  dependencies with phase gates.
- Listed decisions, compute, storage, data, and human-review resources.
- Added explicit risks, loopholes, dependency graph, and out-of-scope limits.
- Added the initial `README.md` and linked the plan from the directory map.

**Verification:**

- Plan acceptance tests are concrete commands or observable artifacts for
  every phase.
- Phase order puts model feasibility before downstream implementation.
- No dependencies were installed and no external data was collected.

**Manual review needed:**

- Approve or revise the phase boundaries, dependency candidates, and resource
  assumptions before Phase 0 implementation.

## Privacy cleanup: public scope boundary

**Status:** Complete

**Changed:**

- Removed organization-specific role, interview, and superseded-project
  context from `PROJECT_SCOPE.md`.
- Kept `PROJECT_SCOPE.md` focused on the project objective, boundaries,
  architecture, evaluation, and deliverables.
- Added `AGENTS.md` to `.gitignore` and marked it local-only in the directory
  map.

**Verification:**

- Repository search found no remaining organization-specific or role-specific
  references.
- Confirmed `AGENTS.md` is ignored while remaining available locally.
- Confirmed the scope heading sequence remains consistent.

## Intent finalization: reusable GTM agent

**Status:** Ready for manual review

**Changed:**

- Replaced the single fictional product/ICP assumption with configurable
  product and ICP inputs.
- Added form-driven onboarding, researched product profiles, claim approval,
  prospect discovery/ranking, user prospect selection, and final draft review.
- Set B2B email as the initial channel.
- Set Colab as the MVP environment for model benchmarking, training,
  evaluation, and temporary authenticated session inference. The transport
  portion of this decision was later superseded by the Phase 1 boundary
  revision below.
- Deferred permanent model hosting and automatic sending until after the MVP.
- Added a multi-product/ICP generalization benchmark and a reviewed-data pilot.
- Reworked the implementation plan into ten dependency-ordered phases.
- Added the React/TypeScript frontend responsibility to the directory map.

**Verification:**

- Scope and implementation phases describe the same workflow and runtime
  boundary.
- The old open questions and single-scenario assumptions were removed.
- Every implementation phase has a concrete acceptance condition, automated
  checks, and a manual gate.
- No dependencies were installed and no external data was collected.

**Manual review needed:**

- Confirm the revised public scope and roadmap before Phase 0 dependency
  selection and scaffolding.

## Phase 0: Reproducible project foundation

**Status:** Ready for manual review

**Changed:**

- Pinned the project to uv-managed Python 3.12 and added `pyproject.toml` plus
  `uv.lock`.
- Added a minimal FastAPI application, validated environment settings, and
  backend smoke tests.
- Added a React/TypeScript/Vite frontend with Vitest, Testing Library, type
  checking, linting, and a production build.
- Removed unused Vite starter assets and added project-specific page metadata
  and a lightweight favicon.
- Added `.env.example` without credentials and expanded artifact exclusions.
- Added separate backend and frontend GitHub Actions quality jobs.
- Added cross-platform line-ending rules and practical setup/run/test commands.

**Verification:**

- Backend tests: `3 passed`.
- Backend lint: clean.
- Frontend tests: `1 passed`.
- Frontend lint and type check: clean.
- Frontend production build: successful.
- Python lockfile check: current.
- Production npm dependency audit: zero known vulnerabilities.
- Public-reference and tracked-secret scans: clean.

**Manual review needed:**

- Run the backend and frontend using the README instructions.
- Confirm the frontend foundation screen renders and `/health` returns the
  documented JSON response.

### CI import-path correction

- Reproduced the Linux CI collection failure locally with the exact
  `uv run pytest -q` command.
- Configured Pytest to add the repository root to its import path so the
  application package resolves consistently from its console entry point.
- Kept CI and the documented local verification command identical.

## Phase 1 boundary revision: Colab result handoff

**Status:** Approved scope correction

**Changed:**

- Kept model benchmarking, QLoRA feasibility, training, evaluation, and real
  base/adapted inference in Colab.
- Removed the public reverse-tunnel and live Colab API requirement because a
  managed Colab runtime is not a reliable or clearly compliant web host.
- Replaced synchronous local-to-Colab calls with strict, versioned, hashed
  inference-result bundles that the local application validates and imports.
- Deferred a live application-to-model transport until a compliant post-MVP
  host is selected.

**Demonstration impact:**

- Real inference and fine-tuned-model results remain demonstrable in Colab.
- The local workflow can evaluate and display those real outputs after bundle
  import.
- Synchronous generation initiated from the local web interface is deferred.

**Verification:**

- Scope, implementation phases, README, environment template, and directory
  responsibilities describe the same Colab-to-local boundary.
- No dependency, runtime code, model artifact, credential, or generated result
  was added by this documentation-only correction.

## Phase 1: Local feasibility package

**Status:** Complete; Qwen3 4B Instruct approved as the fine-tuning base

**Changed:**

- Added strict inference request, response, model identity, runtime metadata,
  and result-bundle contracts.
- Added canonical SHA-256 integrity checks, request/revision matching, duplicate
  rejection, and a size-bounded local bundle reader.
- Added a deterministic inference test double for later local workflows.
- Added a fixed nine-case benchmark spanning three product categories and
  three ICP patterns.
- Pinned Qwen3 4B Instruct and Phi-4 Mini Instruct to immutable revisions and
  recorded their licenses.
- Added hard-gate scoring and a deterministic tie-break rule.
- Added the clean Colab notebook for environment capture, candidate benchmark,
  QLoRA smoke, incremental Drive persistence, human review, and real inference
  bundle export.
- Added the manual Colab runbook and model-comparison report template.

**Automated verification:**

- Strict contracts reject extra fields, non-finite metrics, tampering,
  request/revision mismatches, and duplicate bundles.
- Benchmark tests cover matrix diversity, strict output parsing, unsupported
  claims, hard gates, and deterministic selection.
- Notebook tests verify pinned revisions/dependencies, empty outputs, prohibited
  tunnel absence, and Python syntax for every code cell.
- Backend and notebook suite: 19 tests passed.
- Backend lint passed and the uv lockfile resolved without changes.
- Frontend regression suite: 1 test passed; typecheck, lint, and production build
  passed.
- Production npm dependency audit found zero vulnerabilities.

**Manual verification completed:**

- Ran both exact model revisions on a Colab Tesla T4 using deterministic
  generation and the fixed nine-case benchmark.
- Qwen passed with 18/18 valid outputs, zero unsupported claim IDs, and a
  successful QLoRA smoke test.
- Phi completed QLoRA but failed the strict JSON gate for all 18 outputs and
  was excluded.
- Human review scored Qwen 2.5/5 and approved it as a fine-tuning base while
  recording its CTA, differentiation, and semantic-claim weaknesses.
- Locally validated the real Qwen inference bundle against its request ID,
  immutable model revision, and SHA-256 integrity digest.
- Final repository verification passed 21 backend/notebook tests plus frontend
  test, typecheck, lint, and production build gates.
- Kept candidate reports, generated bodies, adapters, and model files outside
  Git.

## Phase 2: Structured backend walking skeleton

**Status:** Approved

**Changed:**

- Added strict product, ICP, campaign, evidence, claim, approval, prospect,
  positioning, outreach, evaluation, and trace contracts.
- Added the four-state campaign workflow and explicit legal transitions.
- Added deterministic fixture stages that propagate submitted product and ICP
  fields without making live-source or model claims.
- Enforced complete claim decisions, at least one approved claim, selected
  ranked prospects, approved-only draft claims, and resolved evidence.
- Added atomic in-memory aggregate replacement and ordered immutable trace
  records with injectable IDs and timestamps.
- Exposed the minimal FastAPI campaign workflow with explicit 404, 409, and
  422 behavior.
- Added the Phase 2 PowerShell API walkthrough.

**Automated verification:**

- Full backend and notebook suite: 32 tests passed.
- Contract tests cover strict input, first-class approval/evaluation records,
  immutable trace events, and stable JSON timestamps.
- Workflow tests cover legal and illegal transitions, two contrasting product
  and ICP inputs, approval barriers, evidence resolution, complete traces, and
  atomic failure behavior.
- API tests complete the fixture workflow and verify status/error contracts.
- Phase 0 and Phase 1 backend/notebook regression checks remain in the full
  test suite.

**Manual verification completed:**

- Completed the campaign API walkthrough using port 8001 because another local
  Python application occupied the default port 8000.
- Reviewed the proposed claims, ranked fixture prospects, selected prospect,
  validated draft, and passing deterministic evaluation.
- Confirmed the complete ordered trace contains all ten expected events from
  `campaign_created` through `draft_evaluated`.

## Phase 3: Product onboarding and claim review

**Status:** Approved

**Changed:**

- Added normalized product and ICP form contracts with per-item bounds,
  duplicate rejection, and controlled-character validation.
- Kept proposed claim text immutable and added exact reviewed wording,
  evidence references, wording source, and evidence-attestation audit fields.
- Added complete/campaign-owned decision enforcement, process-local mutation
  locking, identical-retry idempotency, and conflicting-replay rejection.
- Required positioning and drafts to resolve both approved claim IDs and their
  matching approval IDs; deterministic generation uses reviewed wording.
- Added a typed frontend API boundary with response ownership, uniqueness,
  state, evidence-resolution, and approval-provenance guards.
- Added the accessible product/ICP form, fixture profile/evidence display,
  approve/reject/edit controls, pending/all-rejected barriers, completion
  ledger, and second-campaign reset.
- Added the configurable Vite API proxy and Phase 3 browser runbook.

**Automated verification:**

- Full Python regression suite: 46 tests passed.
- Backend Ruff lint: clean.
- Frontend suite: 15 tests passed across API, form, review, and application
  behavior.
- Frontend typecheck and Oxlint: clean.
- Frontend production build: successful.
- No Python or npm dependency was added.

**Manual verification completed:**

- Completed the browser walkthrough with the contrasting logistics and
  cybersecurity product/ICP configurations.
- Confirmed the pending and all-rejected barriers, edited-wording attestation,
  completion ledger, and clean second-campaign reset.
- User approved Phase 3 after manual verification.

## Phase 4: Multi-source prospect discovery and research

**Status:** Accepted after manual verification

**Changed:**

- Added strict research-run, collection-attempt, ranking-factor, signal,
  evidence-provenance, and selected-prospect profile contracts.
- Moved the already locked `httpx2` package into runtime dependencies.
- Added exact-host HTTPS admission, public-only DNS validation, redirect
  revalidation, robots enforcement, per-host limits, bounded retries/content,
  contact-data stripping, response hashing, and an ignored SQLite cache.
- Added structured Wikidata industry resolution plus bounded company queries,
  optional approved market-seed discovery, official-site admission, and
  three-page candidate expansion.
- Added deterministic evidence-supported ranking with separate priority,
  quality, completeness, uncertainty, and unknown factors.
- Added bounded twelve-page selected-company research with section coverage,
  citations, warnings, and failed collection records.
- Changed selection to `awaiting_prospect_research` and required a completed,
  same-run profile before positioning or draft generation.
- Added request idempotency, one-active-run guards, stale-apply checks, retained
  failed runs, and RFC-style 502/503 research problems.
- Added the research workspace for live seeds, candidate evidence, selection,
  deep research, covered/unknown sections, and an explicit Phase 4 stop.
- Added the Phase 4 specification, source policies, and manual runbook.

**Automated verification:**

- Full Python regression suite: 87 tests passed.
- Backend Ruff lint and uv lockfile checks: clean.
- Frontend suite: 18 tests passed across six files.
- Frontend typecheck, Oxlint, and production build: successful.
- No new package was added; the pre-existing locked HTTP client moved from the
  development group to runtime.

**External review:**

- Codex CLI approved the revised multi-source plan with no blockers after the
  narrow Wikidata-only draft was replaced by staged discovery, shallow official
  expansion, and selected-prospect deep research.

**Manual verification completed:**

- User completed a live market-discovery run successfully.
- User completed fixture deep research for a selected company successfully.
- User accepted Phase 4 while explicitly carrying regional targeting, company-
  feature coverage, and plain-language report usability into the required
  follow-up gate documented in `docs/IMPLEMENTATION_PLAN.md`.

**Manual-verification fix:**

- Reproduced a live discovery failure caused by `https://cpr.ca/` redirecting
  outside its admitted host set.
- Preserved the SSRF-safe redirect boundary while changing optional official-
  site policy denials into candidate warnings instead of campaign failures.
- Added sanitized `source_policy_denied` reporting and regression coverage for
  candidate preservation and warning propagation.
- Re-ran the exact three-industry logistics ICP against live public sources:
  discovery completed with 10 prospects, 27 evidence records, and explicit
  per-site warnings for inaccessible optional expansions.
- Fixed large live runs exceeding the bounded trace-event output list. Trace
  events now reference the authoritative research run, which retains every
  prospect and evidence ID with campaign-level ownership validation.

## Phase 4 follow-up: Regional targeting and readable research

**Status:** Automated verification complete; manual verification pending

**Changed:**

- Added optional multi-region ICP input throughout the form, API, fixture, and
  campaign contracts.
- Added region-aware Wikidata queries and a hard ranking eligibility gate.
  Region-scoped discovery excludes candidates without explicit matching public
  evidence and never infers geography from names or domains.
- Extended selected-company research to follow relevant second-level links
  while retaining the twelve-page cap, source policy, and failure records.
- Added five short, human-readable finding sections with separated unknowns,
  citations, source language, summary language, and translation status.
- Added an optional authenticated Colab translation client. It uses existing
  HTTP tooling, reads its secret from the environment, rejects insecure endpoint
  configuration, and reports model downtime as unavailable translation.

**Automated verification:**

- Full Python suite: 99 tests passed.
- Frontend suite: 19 tests passed across six files.
- Backend Ruff, frontend typecheck, and frontend Oxlint: clean.
- No new dependency was added.

## Phase 4.1: Fast and recoverable public research

**Status:** Automated verification complete; manual verification pending

**Changed:**

- Replaced broad Wikidata entity and company matching with exact submitted-term
  resolution and a bounded subquery that limits candidates before English label
  resolution.
- Preserved `source_timeout`, `source_failure`, and `no_candidates` as distinct
  outcomes instead of collapsing failed sources into an empty-market result.
- Ran independent discovery providers and up to ten unique official-site
  expansions concurrently within a shared fifteen-second deadline.
- Added optional Brave Search discovery using only submitted industry and region
  terms. Search results remain hints until official-site evidence is retained.
- Added permanent cross-domain recovery for structured official-site records,
  while retaining HTTPS, public-DNS, robots, hop, content, and identity gates.
- Added focused HTML extraction and selected-company sitemap fallback when the
  homepage contains no useful research navigation.
- Added and locked Trafilatura 2.2.0, RapidFuzz 3.14.5, and tldextract 5.3.1.
  Public-suffix updates are disabled at runtime in favor of the packaged
  snapshot.

**Automated verification:**

- Full Python suite: 116 tests passed.
- Frontend suite: 19 tests passed across six files.
- Backend Ruff, frontend Oxlint, frontend typecheck, and production build:
  successful.
- `uv lock --check`: clean with 47 resolved packages.
- Live Wikidata timing sample for logistics in the United States: 10 bindings
  in 1.43 seconds using the production label-free SPARQL shape. Public endpoint
  timing remains variable and is not asserted in CI.
