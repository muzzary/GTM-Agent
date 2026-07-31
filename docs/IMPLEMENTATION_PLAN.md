# GTM-Agent Implementation Plan

## Outcome

Given a fictional product and a prospect profile, one local command should
produce a source-backed positioning brief, a structured outreach draft, an
evaluation report, and—only when approved by a human—a revised draft.

This plan turns `PROJECT_SCOPE.md` into implementation checkpoints. Each phase
must pass its automated checks, receive self-review, be manually reviewed by
the user, and then be committed and pushed before the next phase begins.

## Current gate: scope approval

Before implementation starts, resolve the six open questions in
`PROJECT_SCOPE.md`: product, ICP, channel confirmation, model/license, source
domains, and reviewed-example target. No dependency installation or external
data collection is required for this planning phase.

## Phase 0 — Decisions and reproducible foundation

**Proves:** The project has an approved product, ICP, data policy, model
candidate, and repeatable local development commands.

**Builds on:** Scope approval only.

**Tasks:**

- Record decisions and boundaries in the project docs.
- Add the Python package metadata, lockfile strategy, test/lint commands, and
  lightweight CI workflow.
- Add safe example environment configuration without secrets.

**Acceptance:** A clean checkout can create the approved Python environment,
run `python -m pytest -q`, run the linter, and execute a smoke command with no
external credentials.

**Automated checks:** Environment bootstrap, empty test suite smoke test,
configuration validation, and CI workflow syntax review.

**Manual gate:** Confirm the selected product, ICP, model, source policy, and
dependency list.

## Phase 1 — Local model feasibility spike

**Proves:** The candidate open model can run in the available local/Colab
resources and reliably produce parseable structured output.

**Builds on:** Phase 0.

**Tasks:**

- Download/load the candidate model through an explicit local cache.
- Run a minimal prompt that requests the outreach schema.
- Record latency, peak memory, malformed-output rate, and license/access notes.

**Acceptance:** A fixture prompt produces valid structured output within the
agreed retry limit on the target machine; the report records the hardware and
model revision used.

**Automated checks:** Output parsing, schema rejection, retry-limit, and
deterministic fixture tests.

**Manual gate:** Review one successful and one deliberately malformed output.

**Risk gate:** If the model is too slow, too large, inaccessible, or legally
unsuitable, stop and choose another approved candidate before building on it.

## Phase 2 — Walking skeleton: structured pipeline

**Proves:** Product context and prospect input can cross every application
layer once and produce a reviewable result without live web access.

**Builds on:** Phase 1.

**Tasks:**

- Implement product, prospect, evidence, positioning, outreach, and evaluation
  schemas.
- Add small fictional fixtures and deterministic evidence.
- Connect positioning → outreach → evaluation through a local CLI.

**Acceptance:** `python -m src.runtime.pipeline --input tests/fixtures/example.json`
creates validated JSON artifacts for positioning, outreach, and evaluation.

**Automated checks:** Schema, transform, serialization, and end-to-end fixture
tests.

**Manual gate:** Review the complete artifact chain and field names.

## Phase 3 — Evidence store and permitted research

**Proves:** Public evidence can be collected or supplied manually with
provenance, caching, rate limits, and citation-safe retrieval.

**Builds on:** Phase 2.

**Tasks:**

- Implement JSONL or SQLite evidence storage.
- Add URL, title, timestamp, content hash, source status, and excerpt records.
- Implement an explicit source allowlist, cache, rate limiter, and fixture
  collector.
- Separate facts, inferences, and unknowns in retrieval results.

**Acceptance:** A fixture collection stores provenance and repeated collection
uses the cache; unsupported claims are flagged with a clear reason.

**Automated checks:** Collector fixtures, cache behavior, hash stability,
allowlist/rate-limit enforcement, citation coverage, and unsupported-claim
tests.

**Manual gate:** Review source policy and sample citations before any real
domain is collected.

## Phase 4 — Baseline outreach generation

**Proves:** The prompt-only base model can generate useful, evidence-aware
outreach against a held-out fixture set.

**Builds on:** Phases 1–3.

**Tasks:**

- Define the prompt contract and structured output parser.
- Generate subject, body, CTA, claims-used, evidence, and uncertainty fields.
- Save prompts, model revision, seed/configuration, and baseline outputs.

**Acceptance:** The baseline produces valid output for the agreed test set,
flags missing evidence instead of inventing claims, and creates a reproducible
baseline report.

**Automated checks:** Valid JSON rate, claim-support checks, unsupported-claim
regressions, and output fixture snapshots.

**Manual gate:** Review a sample set for relevance, clarity, tone, and CTA.

## Phase 5 — Reviewed dataset and one outreach adapter

**Proves:** A reviewed, leakage-safe dataset and one LoRA/QLoRA adapter improve
the agreed outreach criteria without weakening factuality.

**Builds on:** Phase 4.

**Tasks:**

- Create reviewed examples with provenance and review labels.
- Split by prospect/company identity to prevent leakage.
- Train the single outreach adapter in Colab or another approved GPU runtime.
- Store training configuration, revision identifiers, and artifacts outside Git.

**Acceptance:** Training completes, the split is leakage-checked, and a
base-versus-adapter report is reproducible on held-out examples.

**Automated checks:** Dataset schema, duplicate/prospect split checks,
configuration checks, and evaluation regression tests.

**Manual gate:** Review the dataset quality and compare base versus adapter
outputs. Do not add a second adapter without evidence of a distinct failure.

## Phase 6 — Campaign evaluator and revision loop

**Proves:** The evaluator detects deliberately inserted weaknesses and the
agent can revise a draft without losing evidence support.

**Builds on:** Phases 3–5.

**Tasks:**

- Encode the 1–5 rubric for relevance, clarity, differentiation, credibility,
  CTA quality, and brand fit.
- Add deterministic checks and model-assisted scoring where justified.
- Add bounded revision with explicit failure reasons and human approval state.

**Acceptance:** Flawed fixtures are flagged, valid drafts are not systematically
punished, scores/reasons are structured, and revision stops after the configured
limit.

**Automated checks:** Deliberate-flaw detection, false-praise/false-criticism
fixtures, score-range validation, and bounded-retry tests.

**Manual gate:** Compare evaluator results with human ratings.

## Phase 7 — Orchestration and local serving

**Proves:** The full research → positioning → outreach → evaluation → revision
workflow is runnable locally with explicit failures and human approval before
export.

**Builds on:** Phases 2–6.

**Tasks:**

- Add controlled orchestration and intermediate artifact recording.
- Add the CLI as the primary interface.
- Add a FastAPI/uvicorn endpoint only if the CLI contract is stable.
- Add timeout, retry, tool-error, and human-approval handling.

**Acceptance:** One mocked end-to-end run completes from input to approved
draft; a tool failure is visible and does not silently produce a sendable
result.

**Automated checks:** Mocked integration tests, failure-path tests, approval
state tests, and CLI/API contract tests.

**Manual gate:** Run the five-minute demo locally and inspect all artifacts.

## Phase 8 — Evaluation package and interview release

**Proves:** Another engineer can reproduce the demo and understand its limits.

**Builds on:** Phase 7.

**Tasks:**

- Complete README setup, usage, limitations, architecture diagram, phase log,
  failure analysis, and evaluation report.
- Add a clean-environment smoke run and final CI checks.
- Confirm no secrets, private data, model weights, or unreviewed artifacts are
  tracked.

**Acceptance:** A clean-environment run follows the README and reproduces the
  documented demo and evaluation outputs.

**Automated checks:** Full test suite, lint, type checks if adopted, CI run,
  secret scan, and repository artifact check.

**Manual gate:** Interview rehearsal and final scope review.

## Dependency plan

Versions should be selected and locked in Phase 0 after the model and Python
version are approved. The list below is a candidate inventory, not permission
to install everything.

### Required baseline candidates

| Dependency | Use | Scope |
| --- | --- | --- |
| Python 3.11 or 3.12 | Runtime | Local + CI |
| `pydantic` | Input/output schemas and validation | Runtime |
| `typer` | Local CLI | Runtime |
| `httpx` | Controlled HTTP collection | Runtime, Phase 3 |
| `pytest` | Automated tests | Development/CI |
| `ruff` | Linting and formatting | Development/CI |

Python standard-library modules should cover JSONL/SQLite, hashing, paths,
timestamps, logging, retries that are simple enough to own, and local file
handling before more packages are added.

### Model and training candidates

| Dependency | Use | Scope | Constraint |
| --- | --- | --- | --- |
| `torch` | Local inference/training backend | Local + Colab | Confirm Windows hardware path. |
| `transformers` | Model/tokenizer loading | Local + Colab | Confirm model compatibility. |
| `accelerate` | Device/runtime configuration | Local + Colab | Required only when the model path needs it. |
| `safetensors` | Safe model artifact format | Local + Colab | Prefer over ad hoc weight formats. |
| `datasets` | Training/evaluation dataset handling | Colab | Add only when Phase 5 starts. |
| `peft` | LoRA/QLoRA adapter training/loading | Colab + local adapter loading | One adapter only initially. |
| `trl` | Optional supervised fine-tuning utilities | Colab | Add only if the training loop needs it. |
| `bitsandbytes` | Optional 4-bit quantization | Colab/Linux first | Do not assume reliable Windows support. |

### Optional serving and measurement candidates

| Dependency | Use | Gate |
| --- | --- | --- |
| `fastapi` + `uvicorn` | Local HTTP serving | Add after CLI contract is stable. |
| `numpy` | Numeric metrics | Add if metrics cannot stay in the standard library. |
| `scikit-learn` | Selected evaluation metrics | Add only for a demonstrated metric need. |
| `pandas` | Tabular analysis/reporting | Optional; avoid for simple JSONL reports. |
| `pytest-cov` | Coverage reporting | Add when coverage thresholds are defined. |
| `mypy` | Static typing | Optional; decide in Phase 0. |

### Tooling and infrastructure

- Git and a GitHub repository with Actions enabled.
- PowerShell and a supported Python installation on Windows.
- Optional Colab account/runtime for adapter training.
- Optional Hugging Face account and accepted model terms if required by the
  selected model.
- No paid LLM API, email provider, CRM, or production hosting is required for
  the MVP.

## Resources required

### Decisions and human resources

- One approved fictional software product with verified demo claims and known
  limitations.
- One narrowly defined ICP and one B2B email channel.
- An allowlist of public source domains and a collection policy.
- A reviewed example target and reviewer rubric; the exact number is an open
  decision, not an assumption.
- Human review time for every phase gate, especially dataset and evaluation
  quality.

### Compute and storage

- Windows development laptop for Python, tests, CLI, and local inference.
- Enough local disk for a Python environment, model cache, fixtures, and
  generated reports; the exact model-dependent budget must be measured in
  Phase 1.
- Optional Colab GPU for LoRA/QLoRA training; training is not assumed to run
  on the Windows laptop.
- A fixed seed/configuration and a record of model revision for reproducible
  comparisons.

### Data and evidence

- Fictional product and prospect fixtures for tests.
- Public, permitted source pages or manually supplied documents.
- Source URLs, timestamps, hashes, excerpts, and review labels.
- No private, login-gated, paywalled, CAPTCHA-protected, or unnecessary
  personal data.

## Dependency graph

```text
Scope decisions
    ↓
Environment + CI + schemas
    ↓
Local model feasibility ─────────────┐
    ↓                               │
Fixture pipeline + evidence store   │
    ↓                               │
Baseline outreach ───────────────┐  │
    ↓                            │  │
Reviewed dataset + adapter       │  │
    └───────────────┬────────────┘  │
                    ↓               │
              Evaluator + revision  │
                    ↓               │
              Orchestration + CLI/API
                    ↓
              Reproducible release
```

## Risks and loopholes

- **Model feasibility:** A candidate may be too slow, incompatible, or
  license-restricted. Phase 1 is a hard gate.
- **Windows/Colab mismatch:** A training dependency may work in Colab but not
  locally. Keep training and inference environments explicit.
- **Source permissions:** “Public” does not automatically mean permitted to
  collect. Require allowlists and manual policy review.
- **Evaluator bias:** A model evaluator can praise fluent but unsupported
  text. Keep deterministic evidence checks and deliberately flawed fixtures.
- **Dataset leakage:** Splitting individual examples randomly can put the same
  prospect in train and test. Split by company/prospect identity.
- **Dependency sprawl:** The scope names a large possible stack. Add packages
  only when a phase acceptance test demonstrates the need.
- **Scope drift:** Keep one product, one ICP, one channel, and one adapter until
  the baseline-versus-adapter claim is defensible.

## Explicitly out of scope

- Automatic email sending, CRM integration, mass outreach, and production
  deployment.
- Training a foundation model or building multiple adapters before proving one.
- Hosted inference as a required path or paid LLM APIs.
- Real customer claims, private datasets, or conversion/virality claims.
- UI/dashboard work before the CLI workflow is stable.
