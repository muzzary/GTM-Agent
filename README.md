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

Phase 0 provides a reproducible Python/FastAPI and React/TypeScript foundation.
The current UI and `/health` endpoint are smoke paths; campaign behavior begins
in later phases.

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

Open the URL printed by Vite. The API health check is available at
`http://127.0.0.1:8000/health`.

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
