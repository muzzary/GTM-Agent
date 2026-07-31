# Directory Map

This map describes the intended repository layout for the GTM Outreach
Intelligence Agent. It is kept intentionally small during the scope-and-
scaffold stage and should be updated as responsibilities become real.

## Root files

| Path | Purpose |
| --- | --- |
| `AGENTS.md` | Local-only repository working rules; intentionally gitignored. |
| `DIRECTORY_MAP.md` | This map of files, directories, and responsibilities. |
| `README.md` | Concise project overview and links to the scope and implementation plan. |
| `PROJECT_SCOPE.md` | Project direction, boundaries, phases, and open questions. |
| `.gitignore` | Prevents local data, secrets, caches, model files, and build output from entering Git. |

## Application code

| Path | Responsibility |
| --- | --- |
| `src/data/` | Collection, normalization, caching, and provenance handling. |
| `src/schemas/` | Structured records for products, prospects, evidence, and campaigns. |
| `src/research/` | Retrieval, evidence selection, and positioning workflows. |
| `src/outreach/` | Prompts, local model loading, generation, and output parsing. |
| `src/evaluation/` | Rubrics, metrics, regression checks, and comparison reports. |
| `src/runtime/` | Orchestration and the local CLI/API serving path. |

## Verification and experiments

| Path | Responsibility |
| --- | --- |
| `tests/` | Unit, fixture-based, integration, and regression tests. |
| `notebooks/` | Reproducible Colab experiments and fine-tuning notebooks. |

## Data and deliverables

| Path | Responsibility |
| --- | --- |
| `data/` | Gitignored local evidence, fixtures, and prospect/product inputs. |
| `results/` | Gitignored generated samples, metrics, and evaluation outputs unless a reviewed report is intentionally committed. |
| `docs/` | Implementation plan, architecture, phase logs, interview notes, failure analysis, and decisions. |
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
