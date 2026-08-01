# Project Scope: GTM Outreach Intelligence Agent

Status: approved for phased implementation.

## 1. Objective

Build a reusable GTM agent that can support different B2B products and ideal
customer profiles (ICPs) without hard-coding one company, product, or market.

The system will:

1. Accept product details, a short product description, and an ICP through a
   structured user form.
2. Research permitted public sources and propose a normalized product profile.
3. Present product claims and limitations for human approval before they can
   influence outreach.
4. Discover and rank prospect companies that match the approved ICP.
5. Let the user select a prospect for deeper evidence-backed research.
6. Produce a positioning brief and personalized B2B email.
7. Evaluate and revise the draft with bounded retries and visible reasons.
8. Require human approval before a draft can be exported.

The system is a research and decision-support artifact, not an autonomous
email sender.

## 2. Confirmed decisions

1. The architecture is product-agnostic and ICP-agnostic. Products and ICPs
   are runtime inputs, not code-level assumptions.
2. The initial outreach channel is personalized B2B email.
3. A user starts a campaign by completing a structured product and ICP form.
4. The agent may research and propose product facts, but only user-approved
   claims can be used in positioning or outreach.
5. The agent discovers and ranks prospect companies; the user chooses which
   prospect receives deeper research and outreach generation.
6. Research may use any permitted public source that passes source-policy,
   access, privacy, and provenance checks.
7. The base model will be selected through a Colab feasibility benchmark for
   business reasoning, structured output, license suitability, latency, and
   available GPU memory.
8. Training, evaluation, and model inference remain in Google Colab for the
   MVP. Quantization may be used when needed.
9. Real base-model and adapter inference is demonstrated inside Colab. Colab
   exports versioned, hashed inference-result bundles that the local application
   validates and imports; the MVP does not expose a public Colab endpoint.
10. Permanent model hosting is a post-MVP decision and will be reassessed after
    the project is complete.
11. Training data may combine permitted public business/outreach datasets,
    reviewed synthetic examples, marketing principles, and product-selling
    scenarios. Every training example used must pass the project review rules.

## 3. Target user and workflow

### Target user

A founder, GTM engineer, sales operator, or marketing operator who needs to
turn product context into evidence-backed prospecting and personalized B2B
outreach.

### Primary workflow

```text
Product + ICP form
        |
        v
Public research and proposed product profile
        |
        v
Human approval of claims and limitations
        |
        v
Prospect discovery and ranking
        |
        v
User selects a prospect
        |
        v
Deep research and evidence collection
        |
        v
Positioning brief
        |
        v
Manual Colab outreach-model run
        |
        v
Validated inference-result bundle
        |
        v
Campaign evaluator and bounded revision
        |
        v
Human-approved exportable draft
```

## 4. Scope of the MVP

### In scope

- Configurable product and ICP inputs.
- One initial channel: personalized B2B email.
- A small React and TypeScript form for product/ICP input, claim approval,
  prospect selection, and draft review.
- A Python/FastAPI backend for schemas, orchestration, research, evaluation,
  and validation/import of Colab inference-result bundles.
- Product-profile research and human claim approval.
- Prospect discovery, ranking, and user selection.
- Public competitor pages, product documentation, company pages, public
  reports, public reviews, and trend material where collection is permitted.
- Source URLs, collection timestamps, content hashes, excerpts, and citations.
- A local evidence store using JSONL or SQLite.
- Structured JSON output and trace records for every agent stage.
- One LoRA/QLoRA outreach adapter trained on reviewed examples.
- Real base-model and adapted-model inference demonstrations in Colab.
- Versioned, hashed result bundles for reviewed handoff to the local workflow.
- A campaign evaluator with deterministic checks and a human-defined rubric.
- Bounded revision, explicit failures, and human approval gates.
- Automated schema, transformation, collection, orchestration, API-contract,
  model-output, and evaluation tests.
- A prompt-only base-model versus adapted-model benchmark.
- Generalization evaluation across multiple product and ICP combinations.
- A concise README, architecture diagram, phase log, evaluation report, and
  repeatable project walkthrough.

### Explicitly out of scope

- Automatic email sending.
- Spam, mass outreach, or evasion of provider limits.
- Login-gated, paywalled, private, or CAPTCHA-protected collection.
- Collection of unnecessary personal data.
- Production CRM integration.
- Permanent or production-grade model hosting during the MVP.
- Paid LLM APIs as a required dependency.
- Claims about actual sales conversion or virality.
- Training a foundation model from scratch.
- Multiple fine-tuned adapters before one adapter demonstrates measurable
  value.
- Treating public or model-generated text as automatically true.

## 5. System architecture

### Components

1. **Web interface**
   - captures product details, short description, ICP, and campaign settings
   - displays proposed claims for approval
   - displays ranked prospects and evidence
   - supports prospect selection and final draft approval

2. **Product profile service**
   - validates user input
   - researches product context
   - proposes capabilities, limitations, target problems, and claims
   - records approval status for every claim

3. **Research collector**
   - fetches permitted public pages or manually supplied documents
   - enforces source policy, timeouts, rate limits, and caching
   - stores URL, title, timestamp, content hash, and collection status

4. **Evidence and retrieval layer**
   - searches collected documents
   - returns source excerpts with citations
   - distinguishes facts, inferences, and unknowns
   - prevents unapproved product claims from entering downstream prompts

5. **Prospect discovery and ranking agent**
   - searches for companies matching the approved ICP
   - ranks candidates with evidence and uncertainty
   - records why each prospect matches or fails the ICP

6. **Positioning agent**
   - identifies prospect pain hypotheses
   - compares approved product capabilities with prospect evidence
   - produces a structured positioning brief

7. **Colab model workspace**
   - loads the selected base model and outreach adapter
   - runs benchmark, training, evaluation, and real inference demonstrations
   - exports structured result bundles that follow the inference contract
   - records model revision, adapter revision, latency, and failures

8. **Campaign evaluator**
   - validates schema and evidence support
   - scores relevance, clarity, differentiation, credibility, CTA quality,
     and brand fit
   - explains failures and requests bounded revision where appropriate

9. **Agent runtime**
   - controls tool permissions and workflow state
   - records traces and intermediate artifacts
   - handles missing, malformed, mismatched, or duplicate result bundles
   - supports base-versus-adapter shadow comparisons
   - stops for human approval at claim, prospect, and final-draft gates

10. **Local API and storage**
    - exposes the application contract through FastAPI
    - stores non-secret campaign state, evidence, traces, and evaluations
    - keeps secrets in local environment variables only

## 6. Model and inference strategy

### Base-model selection

Do not commit to a model before benchmarking candidates in Colab. Select the
best open instruction-tuned model that satisfies all of these constraints:

- license permits the intended public demonstration
- fits the available Colab GPU for inference and LoRA/QLoRA training
- follows structured business instructions reliably
- produces concise, credible B2B writing
- handles evidence and uncertainty without inventing facts
- provides acceptable latency and memory usage
- supports quantization when needed

### Adapter strategy

The first adapter is an **outreach adapter**. It targets:

- professional B2B tone
- concise email structure
- product/ICP generalization
- evidence-aware personalization
- clear calls to action
- refusal to invent missing facts

Research, ranking, and evaluation do not receive separate adapters initially.
They use tools, retrieval, schemas, deterministic checks, and prompts. Another
adapter requires evidence of a distinct, repeatable failure that fine-tuning
can solve.

### Colab inference and artifact boundary

Training, evaluation, and model inference run in Colab. Model artifacts are
stored in an approved persistent location such as private cloud storage or a
model repository; secrets are never stored in the notebook.

The MVP does not expose a public web service or reverse tunnel from a managed
Colab runtime. Instead, a user manually runs real inference in the notebook and
exports a versioned result bundle containing the request identifier, contract
version, structured output, model and adapter revisions, generation settings,
latency, and integrity hashes. The local application validates and imports only
reviewed bundles that match the pending request and approved revisions.

This boundary preserves demonstrations of real base-model and fine-tuned-model
inference. It does not provide synchronous local-application-to-model calls.
During automated development the local application uses a contract-compatible
test double; a compliant live host is selected after the MVP.

Colab is not presented as permanent hosting. A separate post-MVP assessment
will compare free or low-cost hosting options and production inference tools.

## 7. Core data contracts

### Campaign input

```json
{
  "product_name": "Example Product",
  "product_url": "https://example.com",
  "short_description": "Automates recurring operational reports.",
  "known_capabilities": ["scheduled reporting"],
  "known_limitations": ["requires source-system access"],
  "icp": {
    "industries": ["logistics"],
    "company_size": "mid-market",
    "roles": ["Head of Operations"],
    "pain_hypotheses": ["manual reporting overhead"]
  }
}
```

### Proposed product claim

```json
{
  "claim_id": "claim-001",
  "claim": "The product supports scheduled reporting.",
  "status": "pending_approval",
  "evidence_ids": ["evidence-001"],
  "uncertainty": "low"
}
```

### Prospect candidate

```json
{
  "company": "Example Logistics",
  "industry": "logistics",
  "matched_icp_fields": ["industry", "company_size"],
  "public_signals": ["recent operations expansion"],
  "evidence_ids": ["evidence-002"],
  "score": 0.82,
  "uncertainty": "medium"
}
```

### Training example

```json
{
  "input": {
    "approved_product_profile": "...",
    "selected_prospect": "...",
    "positioning": "...",
    "evidence": ["..."]
  },
  "approved_output": {
    "subject": "...",
    "body": "...",
    "claims_used": ["claim-001"],
    "personalization_evidence": ["evidence-002"]
  },
  "review": {
    "factual": true,
    "relevant": true,
    "approved": true
  }
}
```

Training data must be reviewed. Teacher-generated examples are weak
supervision and cannot become training truth without validation.

## 8. Evaluation strategy

### Generalization benchmark

Evaluate across a product/ICP matrix rather than one hard-coded scenario. The
initial benchmark should include at least three distinct product categories
and three distinct ICP patterns, with company/prospect separation across data
splits.

### Outreach generation

Compare the prompt-only base model with the adapted model on a held-out set.
Measure:

- valid structured-output rate
- approved-claim compliance
- factual claim support
- personalization relevance
- brand/style fit
- unsupported-claim rate
- CTA quality
- latency and peak GPU memory

### Campaign evaluator

Use 1-5 scores for relevance, clarity, differentiation, credibility, CTA
quality, and brand fit. Measure:

- agreement with human reviewers
- consistency on repeated evaluations
- detection of deliberately inserted flaws
- false-praise and false-criticism rates

### Research and prospecting

Measure:

- source citation coverage and correctness
- freshness timestamp presence
- fact/inference/unknown separation
- ICP-match precision on reviewed candidates
- usefulness of ranking explanations
- unsupported claim detection

### Agent runtime and inference

Measure:

- complete trace coverage across agent stages
- malformed-output and retry rates
- missing, malformed, mismatched, and duplicate result-bundle behavior
- tool failure handling
- approval-gate enforcement
- base-versus-adapter shadow comparison
- Colab generation latency and memory
- reproducibility with fixed configuration and revision identifiers

## 9. Implementation phases

The authoritative task-level roadmap is
[`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md). Its phases are:

0. Reproducible project foundation.
1. Colab model, QLoRA, and inference-result feasibility.
2. Structured backend walking skeleton.
3. Product onboarding and claim approval.
4. Public research, prospect discovery, and ranking.
5. Baseline outreach, traces, and evaluation harness.
6. Reviewed dataset and one LoRA/QLoRA adapter.
7. Campaign evaluator, bounded revision, and shadow comparison.
8. End-to-end agent runtime and web workflow.
9. Reproducible evaluation package and release.

Every phase requires automated checks, self-review, user manual verification,
an atomic commit, and a push before the next phase begins.

## 10. Project structure

```text
frontend/           React + TypeScript product/ICP and review workflow
src/
  data/             collection, normalization, caching, provenance
  schemas/          product, ICP, claim, prospect, evidence, campaign models
  research/         product research, retrieval, prospect discovery/ranking
  outreach/         prompts, inference contracts, result-bundle validation
  evaluation/       rubric, metrics, shadow comparison, regression checks
  runtime/          orchestration, workflow state, FastAPI application
tests/              unit, fixture, contract, integration, regression tests
notebooks/          Colab benchmark, QLoRA, training, evaluation, inference demo
data/               gitignored local evidence and working datasets
results/            generated metrics and samples; reviewed reports may commit
configs/            non-secret source, model, runtime, and evaluation config
docs/               architecture, plans, phase logs, reports, limitations
```

## 11. Planned commands

Commands become authoritative when Phase 0 selects and locks the toolchain.
The intended interface is:

```powershell
python -m pytest -q
python -m ruff check .
python -m src.runtime.api
python -m src.evaluation.run --split test
npm --prefix frontend run test
npm --prefix frontend run lint
npm --prefix frontend run build
```

No dependency is installed without approval. Candidate dependencies and phase
gates are listed in `docs/IMPLEMENTATION_PLAN.md`.

## 12. Boundaries

### Always do

- validate user input, public-source content, and model output
- keep unapproved product claims out of downstream prompts
- attach provenance to research evidence and prospect ranking
- record traces, model revisions, prompts, seeds, and evaluation configuration
- keep human approval before claim use and final export
- enforce bounded retries, tool permissions, and explicit failures
- run tests and self-review before every phase commit
- keep secrets in ignored environment files or Colab secret storage

### Ask first

- adding or changing dependencies
- selecting or changing the base model or license
- enabling collection from a source with unclear permission
- storing personal, customer, or CRM data
- changing the B2B email channel
- changing the evaluation rubric or approval gates
- adding automatic sending
- adding any live model host or public inference transport

### Never do

- bypass access controls, paywalls, logins, robots restrictions, or CAPTCHAs
- scrape private pages or unnecessary personal data
- send automated outreach without human approval
- fabricate product claims, competitor facts, or prospect signals
- use pending/rejected claims in outreach
- commit tokens, credentials, private datasets, model weights, or unreviewed
  customer data
- pass unvalidated model output into tools, file paths, queries, or commands
- report synthetic examples as real business outcomes
- remove failing tests to improve reported results

## 13. Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Generality becomes vague or untestable | Benchmark a fixed matrix of product categories and ICP patterns. |
| Colab hardware or sessions vary | Record the allocated hardware/runtime, persist incremental artifacts, and require explicit feasibility thresholds. |
| Result bundle does not match the pending request | Validate request ID, contract version, revisions, schema, and integrity hashes before import. |
| Model quality is insufficient | Benchmark several permitted candidates before selecting one. |
| Too little reviewed training data | Set the pilot size after the baseline, inspect learning curves, and expand where quality or coverage is weak. |
| Product or prospect facts are invented | Require evidence IDs, claim approval, and deterministic support checks. |
| Public collection violates policy | Enforce source review, access rules, rate limits, caching, and provenance. |
| Dataset leakage inflates results | Split by product, company, and prospect identity; report overlap checks. |
| Evaluator rewards fluent unsupported text | Combine deterministic checks, flawed fixtures, and human-rated comparisons. |
| Agent loops or overreaches | Bound retries, constrain tools, record traces, and require approval gates. |
| Dependency sprawl | Add packages only when a phase acceptance test demonstrates the need. |

## 14. Project deliverables

- public reproducible repository with no private context or secrets
- configurable product/ICP onboarding workflow
- claim-approval and prospect-selection workflow
- source-backed prospect research and ranking example
- Colab model benchmark, training notebook, and evaluation notebook
- one trained outreach adapter
- real base-model and adapted-model inference demonstrations in Colab
- validated Colab-to-local inference-result handoff
- base-versus-adapter and generalization evaluation reports
- campaign-quality rubric, traces, regression checks, and failure analysis
- tested Python/FastAPI agent runtime and small React/TypeScript interface
- architecture diagram, setup guide, limitations, and project walkthrough

## 15. Post-MVP decisions

After the MVP is complete and measured:

1. Compare free or low-cost persistent hosting options for the selected model.
2. Evaluate vLLM or another production inference server on compatible hardware.
3. Decide whether CRM integration, another outreach channel, or additional
   adapters are justified by evidence.
