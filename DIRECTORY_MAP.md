# Directory Map

This map describes the intended repository layout for the GTM Outreach
Intelligence Agent. Update it whenever a new top-level responsibility is
introduced.

## Root files

| Path | Purpose |
| --- | --- |
| `AGENTS.md` | Local-only repository working rules; intentionally gitignored. |
| `DIRECTORY_MAP.md` | This map of files, directories, and responsibilities. |
| `README.md` | Concise project overview and links to the scope and implementation plan. |
| `PROJECT_SCOPE.md` | Approved project objective, workflow, boundaries, and architecture. |
| `pyproject.toml` | Python metadata, dependency declarations, and test/lint configuration. |
| `uv.lock` | Exact cross-platform Python dependency lockfile managed by uv. |
| `.python-version` | Project Python version used by uv and CI. |
| `.env.example` | Non-secret environment-variable template. |
| `.gitattributes` | Cross-platform text and line-ending rules. |
| `.gitignore` | Prevents local data, secrets, caches, model files, and build output from entering Git. |
| `.github/workflows/ci.yml` | Backend and frontend quality checks for pushes and pull requests. |

## Application code

| Path | Responsibility |
| --- | --- |
| `frontend/src/api/` | Typed campaign requests, API error normalization, and defensive response validation. |
| `frontend/src/components/` | Accessible onboarding, claim review, prospect ranking, citation, selection, and deep-research components. |
| `frontend/src/forms/` | Pure form normalization and validation rules shared by the onboarding UI. |
| `frontend/src/` | React application shell, responsive styles, test setup, and component tests. |
| `frontend/package.json` | Frontend commands and dependency declarations. |
| `frontend/package-lock.json` | Exact npm dependency lockfile used by local setup and CI. |
| `src/data/` | Controlled HTTP collection, source policy, robots handling, bounded parsing, privacy filtering, and SQLite response caching. |
| `src/agent/` | Strict model-output contracts, allowlisted CRM tool definitions, approval enforcement, bounded execution, and tool-call traces. |
| `src/crm/` | Shared CRM business operations and GTM-to-CRM prospect linking used by HTTP endpoints and agent tools. |
| `src/revenue/` | Revenue event ingestion and effective-time CRM reporting. |
| `src/schemas/` | Structured records for products, prospects, evidence, and campaigns. |
| `src/research/` | Regional Wikidata and approved-market discovery, official-site expansion, transparent ranking, selected-prospect research, and optional Colab-backed English translation. |
| `src/outreach/` | Prompts, inference contracts, result-bundle validation/import, and output parsing. |
| `src/evaluation/` | Rubrics, metrics, regression checks, and comparison reports. |
| `configs/phase1/benchmark.json` | Fixed candidate revisions, generation settings, hard gates, rubric, and 3×3 benchmark matrix. |
| `src/schemas/base.py` | Shared strict, immutable Pydantic model configuration. |
| `src/schemas/campaign.py` | Campaign inputs, immutable claims, authorized reviewed wording, provenance, outreach, evaluation, and trace contracts. |
| `src/runtime/api.py` | FastAPI campaign/research endpoints, live collector composition, and typed problem responses. |
| `src/runtime/fixtures.py` | Deterministic fixture research, ranking, prospect-research gate, positioning, generation, and evaluation stages. |
| `src/runtime/workflow.py` | Campaign state machine, active-run/idempotency controls, research application, approval gates, trace creation, and in-memory repository. |
| `src/runtime/settings.py` | Validated environment configuration. |

## Verification and experiments

| Path | Responsibility |
| --- | --- |
| `tests/` | Backend unit, fixture-based, integration, and regression tests. |
| `notebooks/phase1_colab_feasibility.ipynb` | Pinned Colab benchmark, QLoRA smoke test, environment capture, and real result-bundle export. |
| `docs/PHASE2_API_RUNBOOK.md` | Manual PowerShell walkthrough for the deterministic campaign API. |
| `docs/PHASE3_RUNBOOK.md` | Browser walkthrough and two-product manual acceptance gate for onboarding and claim review. |
| `docs/PHASE3_SPEC.md` | Approved Phase 3 behavior, authorization invariants, risks, and acceptance tests. |
| `docs/PHASE4_SPEC.md` | Approved multi-source research architecture, source controls, ranking semantics, and acceptance tests. |
| `docs/PHASE4_RUNBOOK.md` | Browser walkthrough for live discovery, selection, deep research, and the positioning gate. |
| `docs/PHASE4_FOLLOWUP_SPEC.md` | Regional targeting, broader company coverage, plain-English findings, and translation contracts. |
| `docs/PHASE4_1_SEARCH_SPEC.md` | Fast multi-source discovery, redirect recovery, extraction, safety, and performance contracts. |
| `docs/CRM_MVP_PLAN.md` | Dependency-ordered plan for the agent-first CRM and revenue MVP extension. |
| `docs/CRM4_RUNBOOK.md` | Manual verification for reviewed prospect-to-company CRM linking. |
| `docs/CRM5_RUNBOOK.md` | Manual verification for revenue events, reports, forecasts, and warnings. |

## Data and deliverables

| Path | Responsibility |
| --- | --- |
| `data/` | Gitignored local evidence, fixtures, and prospect/product inputs. |
| `results/` | Gitignored generated samples, metrics, and evaluation outputs unless a reviewed report is intentionally committed. |
| `docs/` | Implementation plan, architecture, phase logs, model/data cards, evaluation, and failure analysis. |
| `configs/` | Versioned non-secret runtime, source-policy, and evaluation configuration. |

## Boundaries

- `src/` contains reusable application code; it should not contain local data
  or generated output.
- `data/` and `results/` are local working areas by default and are ignored by
  Git.
- `notebooks/` may orchestrate experiments but should not become the runtime
  implementation.
- Secrets belong in local environment files, never in source, notebooks, or
  committed configuration.
