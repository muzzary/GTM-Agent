# GTM Outreach Intelligence Agent

This project is a reusable, evidence-backed GTM agent for personalized B2B
email outreach. A user supplies product details and an ICP, approves researched
product claims, selects from ranked prospect companies, and receives an
evaluated personalized draft.

The local React/TypeScript and Python/FastAPI application orchestrates research,
evidence, approvals, evaluation, and workflow state. Model benchmarking,
fine-tuning, evaluation, and real inference run in Google Colab for the MVP.
Colab exports versioned result bundles that the local application validates and
imports. A temporary authenticated Colab endpoint is optional for translating
public research summaries; the core workflow does not depend on its uptime.

Read [PROJECT_SCOPE.md](PROJECT_SCOPE.md) for the product boundary and
[docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) for the phased build
plan, dependency candidates, and required resources.

## Current status

Phase 4 adds bounded multi-source prospect discovery and selected-company
research. Wikidata resolves submitted industries into structured company
queries, optional user-approved market pages contribute candidate domains, and
an optional Brave Search key broadens candidate hints. Validated official sites
provide shallow ranking and deep research evidence; search snippets alone never
become evidence.
Scores, quality, completeness, uncertainty, citations, failed collections, and
unknowns remain separate and visible. Optional ICP regions are hard discovery
eligibility constraints, and deep research now presents short English findings
while preserving the original source excerpts and translation status.

Campaign state remains process-local and is cleared when the backend restarts.
The collector is not an unrestricted web crawler: exact source admission,
public-IP checks, robots rules, rate limits, response bounds, privacy filtering,
and a local ignored SQLite cache apply. Real model generation begins in Phase
5.

Phase 4.1 runs independent discovery sources and bounded official-site
expansions concurrently. Its Wikidata query limits candidates before label
resolution, selected-company research can use a same-host sitemap when normal
navigation is sparse, and permanent company-domain migrations can be recovered
only from structured official-site records with public-DNS and identity checks.

CRM-1 adds the first local CRM foundation: tenant-scoped companies, contacts,
pipelines, stages, deals, activities, custom fields, and idempotent SQLite
persistence. CRM-2 adds tenant-scoped API endpoints and a workspace that turns a
researched prospect into a traceable company, contact, pipeline, deal, and
research activity. CRM-3 adds a dependency-free controlled agent runtime with
validated, allowlisted CRM tools and approval-gated mutations. Colab model
integration remains behind the existing validated inference boundary. The
controlled boundary is available at `POST /agent/runs`; it currently uses the
deterministic test double and can inspect a completed selected prospect. CRM-4
adds a reviewed GTM-to-CRM link operation: it preserves selected-prospect
evidence, records a research activity, detects duplicate normalized domains,
and exposes the mutation as an approval-gated agent tool.
CRM-5 adds a dependency-free revenue event ledger with idempotent ingestion,
effective-time MRR and churn calculations, pipeline value, probability-weighted
forecasting, explainable event IDs, reconciliation warnings, and a read-only
agent report tool.

## Requirements

- Python 3.12
- `uv` 0.11.19 or compatible
- Node.js 24
- npm 11

## Setup

```powershell
uv sync --locked --dev
Set-Location frontend
npm.cmd ci
Set-Location ..
```

Live research requires a non-secret contact identifier in the local process so
public services can identify the client:

```powershell
$env:GTM_RESEARCH_CONTACT = "research-contact@example.com"
```

This value is used only in the collector User-Agent. Credentials remain in
ignored local environment variables or Colab secret storage.

To optionally broaden discovery through Brave Search:

```powershell
$env:GTM_BRAVE_SEARCH_API_KEY = "your-brave-search-api-key"
```

Only submitted industry and region terms are sent. Product details, claims,
roles, pain hypotheses, and collected evidence are not sent to Brave. Without a
key, Wikidata and approved market seeds continue to work normally.

To translate non-English research with the Colab model, configure both values:

```powershell
$env:GTM_TRANSLATION_ENDPOINT = "https://your-colab-tunnel.example/translate"
$env:GTM_TRANSLATION_API_KEY = "your-long-random-secret"
```

The endpoint accepts `task`, `target_language`, and `text`, and returns
`translated_text` plus an ISO `source_language`. The application makes the
short summary locally. If Colab is absent or offline, research still completes
and marks the English translation unavailable.

## Run

Backend:

```powershell
uv run uvicorn src.runtime.api:app --reload
```

Frontend, in a second terminal:

```powershell
Set-Location frontend
npm.cmd run dev
```

If the backend uses port 8001:

```powershell
Set-Location frontend
$env:GTM_API_PROXY_TARGET = "http://127.0.0.1:8001"
npm.cmd run dev
```

Open the URL printed by Vite. By default, the API health check is available at
`http://127.0.0.1:8000/health`; the Phase 2 runbook explains how to use another
local port when 8000 is occupied.

Follow [`docs/PHASE4_RUNBOOK.md`](docs/PHASE4_RUNBOOK.md) for the live discovery,
selection, and deep-research manual gate.

## Campaign and research API

The local fixture workflow exposes these endpoints:

- `POST /campaigns`
- `GET /campaigns/{campaign_id}`
- `POST /campaigns/{campaign_id}/claim-decisions`
- `POST /campaigns/{campaign_id}/discovery-runs`
- `GET /campaigns/{campaign_id}/prospects`
- `POST /campaigns/{campaign_id}/prospects/{prospect_id}/select`
- `POST /campaigns/{campaign_id}/prospects/{prospect_id}/research-runs`
- `GET /campaigns/{campaign_id}/research-runs/{run_id}`
- `POST /campaigns/{campaign_id}/draft`
- `GET /campaigns/{campaign_id}/trace`
- `POST /crm/companies`, `GET /crm/companies`
- `POST /crm/pipelines`, `POST /crm/contacts`, `POST /crm/deals`
- `POST /crm/activities`, `GET /crm/activities/{entity_type}/{entity_id}`
- `POST /campaigns/{campaign_id}/crm/company` (reviewed prospect-to-company link)
- `POST /crm/revenue/events`, `GET /crm/revenue/report`
- `POST /agent/runs` (controlled test-double execution boundary)

The draft endpoint remains for fixture regression testing, but Phase 4's UI
stops at `prospect_researched`. Positioning is rejected until a valid selected-
prospect research profile exists.

## Verify

```powershell
uv run ruff check .
uv run pytest -q
Set-Location frontend
npm.cmd run lint
npm.cmd run typecheck
npm.cmd test
npm.cmd run build
```

GitHub Actions runs the same backend and frontend quality gates on every push
and pull request.

## Phase 1 Colab gate

Phase 1 uses a fixed model benchmark, a minimal QLoRA smoke test, and a
versioned inference-result bundle. Follow
[`docs/PHASE1_COLAB_RUNBOOK.md`](docs/PHASE1_COLAB_RUNBOOK.md) to run the real
GPU workload and validate its result locally. Generated reports, model files,
and smoke adapters remain outside Git.
