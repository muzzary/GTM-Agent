# GTM Outreach Intelligence Agent

This project is a reusable, evidence-backed GTM agent for personalized B2B
email outreach. A user supplies product details and an ICP, approves researched
product claims, selects from ranked prospect companies, and receives an
evaluated personalized draft.

The local React/TypeScript and Python/FastAPI application orchestrates research,
evidence, approvals, evaluation, and workflow state. Model benchmarking,
fine-tuning, evaluation, and real inference run in Google Colab for the MVP.
Colab exports versioned result bundles that the local application validates and
imports; the MVP does not expose a public Colab inference endpoint.

Read [PROJECT_SCOPE.md](PROJECT_SCOPE.md) for the product boundary and
[docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) for the phased build
plan, dependency candidates, and required resources.

## Current status

Phase 3 provides the interactive product-onboarding and claim-review workflow.
Users can submit reusable product and ICP details, inspect the deterministic
fixture profile and evidence, then approve, reject, or edit every proposed
claim. Edited wording requires explicit evidence attestation, and the backend
records the exact authorized wording without changing the original proposal.

The workflow intentionally uses process-local in-memory state and fixture
services. Live research begins in Phase 4 and real model generation begins in
Phase 5.

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

No credential is required in Phase 0. Future credentials remain in ignored
local environment variables or Colab secret storage and never in notebooks.

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

Follow [`docs/PHASE3_RUNBOOK.md`](docs/PHASE3_RUNBOOK.md) for the complete
browser walkthrough and the required two-product manual gate.

## Phase 2 campaign API

The local fixture workflow exposes these endpoints:

- `POST /campaigns`
- `GET /campaigns/{campaign_id}`
- `POST /campaigns/{campaign_id}/claim-decisions`
- `GET /campaigns/{campaign_id}/prospects`
- `POST /campaigns/{campaign_id}/prospects/{prospect_id}/select`
- `POST /campaigns/{campaign_id}/draft`
- `GET /campaigns/{campaign_id}/trace`

Campaign state is intentionally process-local and is cleared when the backend
restarts. Follow
[`docs/PHASE2_API_RUNBOOK.md`](docs/PHASE2_API_RUNBOOK.md) for a complete
PowerShell walkthrough.

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
