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
| `.gitignore` | Prevents local data, secrets, caches, model files, and build output from entering Git. |

## Application code

| Path | Responsibility |
| --- | --- |
| `frontend/` | React and TypeScript product/ICP form, claim approval, prospect selection, and draft review. |
| `src/data/` | Collection, normalization, caching, and provenance handling. |
| `src/schemas/` | Structured records for products, prospects, evidence, and campaigns. |
| `src/research/` | Retrieval, evidence selection, and positioning workflows. |
| `src/outreach/` | Prompts, Colab inference client, generation contracts, and output parsing. |
| `src/evaluation/` | Rubrics, metrics, regression checks, and comparison reports. |
| `src/runtime/` | Agent orchestration, workflow state, model routing, and FastAPI application. |

## Verification and experiments

| Path | Responsibility |
| --- | --- |
| `tests/` | Unit, fixture-based, integration, and regression tests. |
| `notebooks/` | Reproducible Colab model benchmarks, training, evaluation, and session-inference notebooks. |

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
