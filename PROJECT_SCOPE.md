# Project Scope: GTM Outreach Intelligence Agent

Status: proposed scope — review and approve before implementation.

## 1. Objective

Build a locally runnable agent system for a hypothetical software company that
wants to understand its market and create evidence-backed personalized
outreach.

The system will:

1. Collect and summarize permitted public market and competitor information.
2. Produce a positioning brief for a selected prospect segment.
3. Generate a personalized outreach draft using a locally served open model.
4. Evaluate the draft against a repeatable marketing-quality rubric.
5. Revise the draft when the evaluator finds unsupported claims, weak
   personalization, poor clarity, or a weak call to action.

The system is a research/demo artifact, not an autonomous sales system.

## 2. Assumptions

These assumptions are explicit and must be corrected before implementation if
they are wrong:

1. The product and company are hypothetical, so no private company data is
   required.
2. The first target channel is personalized B2B email outreach, not mass
   consumer advertising.
3. The first demonstration uses a small, invented software product and a
   small set of fictional prospect profiles grounded in public company
   information.
4. No hosted LLM inference API is used. Open model weights may be downloaded
   from a model repository, but generation runs locally.
5. Google Colab may be used for occasional GPU fine-tuning; the local Windows
   machine remains the development and inference environment.
6. The first fine-tuned adapter is for outreach generation. Research and
   evaluation use tools, retrieval, prompts, and deterministic checks until
   evidence proves another adapter is needed.

## 3. Target user and workflow

### Target user

A founder, GTM engineer, or marketing operator who needs to research a
prospect, decide what message is relevant, draft outreach, and check the draft
before sending it.

### Primary workflow

```text
Product context + verified claims
                ↓
Prospect profile + permitted public sources
                ↓
Research and evidence collection
                ↓
Positioning brief
                ↓
Local outreach model
                ↓
Campaign quality evaluator
                ↓
Human-approved draft
```

## 4. Scope of the MVP

### In scope

- One hypothetical B2B software product.
- One target segment and one outreach channel: B2B email.
- A local evidence store using JSONL or SQLite.
- Public competitor pages, public documentation, public reports, public
  reviews, and public trend material where collection is permitted.
- Source URLs, collection timestamps, content hashes, and citations.
- A positioning brief with evidence and uncertainty.
- A local open-weight language model.
- One LoRA/QLoRA outreach adapter trained on reviewed examples.
- Structured JSON output for every agent stage.
- A campaign evaluator with a human-defined rubric.
- A local API or CLI demo.
- Automated tests for schemas, data transforms, model output parsing, and
  evaluation metrics.
- A benchmark comparing a prompt-only base model with the adapted model.
- A concise README, architecture diagram, phase log, and interview demo.

### Explicitly out of scope

- Automatic email sending.
- Spam, mass outreach, or evasion of provider limits.
- Login-gated, paywalled, private, or CAPTCHA-protected scraping.
- Collection of unnecessary personal data.
- Production CRM integration.
- Paid LLM APIs or hosted inference as a required dependency.
- Claims about actual sales conversion or virality.
- Training a language model from scratch.
- Fine-tuning three adapters before one adapter has demonstrated value.
- Treating scraped text as automatically true.

## 5. System architecture

### Components

1. **Product knowledge store**
   - verified capabilities
   - verified limitations
   - approved claims
   - customer/problem hypotheses

2. **Research collector**
   - fetches permitted public pages or manually supplied documents
   - stores content, URL, title, timestamp, and hash
   - applies rate limits and caching

3. **Evidence and retrieval layer**
   - searches collected documents
   - returns source excerpts with citations
   - distinguishes facts, inferences, and unknowns

4. **Positioning agent**
   - identifies prospect pain hypotheses
   - compares product capability to prospect context
   - produces a structured positioning brief

5. **Outreach model**
   - receives only structured context and verified evidence
   - generates a subject, message, CTA, evidence list, and uncertainty fields

6. **Campaign evaluator**
   - checks schema validity
   - checks evidence support
   - scores relevance, clarity, differentiation, credibility, CTA quality,
     and brand fit

7. **Orchestrator**
   - calls tools in a controlled order
   - records intermediate artifacts
   - retries malformed outputs with clear limits
   - stops for human approval before sending

8. **Serving layer**
   - local CLI first
   - local FastAPI endpoint second
   - vLLM only when the model and hardware path are proven useful

## 6. Model strategy

### Base model

Start with a small open instruction-tuned model suitable for Colab
experimentation and local inference. Gemma 3 270M-it is the initial candidate;
the model is a candidate, not a permanent commitment.

Selection criteria:

- local inference is possible on the available laptop
- the license permits the intended demo use
- the model follows structured instructions reliably
- fine-tuning fits the available GPU budget
- output quality is sufficient for short B2B drafts

### Adapter strategy

The initial adapter is an **outreach adapter**. It learns:

- professional B2B tone
- concise structure
- personalization behavior
- evidence-aware wording
- clear calls to action
- refusal to invent missing facts

The research and evaluator components do not receive adapters initially. They
will use retrieval, prompts, schemas, rules, and evaluation code. A second or
third adapter requires evidence of a repeatable failure that fine-tuning can
solve.

### No hosted inference API

The model is downloaded once, fine-tuned with LoRA/QLoRA, and served locally.
The model repository is storage and distribution infrastructure, not the
generation backend.

## 7. Data specification

### Product record

```json
{
  "product_id": "demo-product",
  "capabilities": ["automated reporting"],
  "verified_claims": ["exports a report in under five minutes"],
  "limitations": ["requires an API integration"],
  "target_segments": ["mid-market logistics teams"]
}
```

### Prospect record

```json
{
  "company": "Example Logistics",
  "industry": "logistics",
  "role": "Head of Operations",
  "public_signals": ["recently expanded operations"],
  "source_urls": ["https://example.com/source"]
}
```

### Training example

```json
{
  "input": {
    "product": "...",
    "prospect": "...",
    "positioning": "...",
    "evidence": ["..."]
  },
  "approved_output": {
    "subject": "...",
    "body": "...",
    "claims_used": ["..."],
    "personalization_evidence": ["..."]
  },
  "review": {
    "factual": true,
    "relevant": true,
    "approved": true
  }
}
```

Training data must be reviewed. Teacher-generated examples may bootstrap the
dataset but are weak supervision, not unquestionable ground truth.

## 8. Evaluation strategy

### Outreach generation

Compare prompt-only base model versus adapted model on a held-out set.

Measure:

- valid JSON rate: target 100% after repair/retry limits
- factual claim support: target 100% on the curated evaluation set
- personalization relevance: human score, target at least 80% acceptable
- brand/style fit: human score, target at least 80% acceptable
- unsupported claim rate: target 0% on verified test cases
- CTA quality: rubric score and reviewer comments

### Campaign evaluator

Create a rubric with 1–5 scores for relevance, clarity, differentiation,
credibility, CTA quality, and brand fit.

Measure:

- agreement with human reviewers
- consistency on repeated evaluations
- ability to identify deliberately inserted flaws
- false praise rate
- false criticism rate

### Research and positioning

Measure:

- source citation coverage
- claim-to-source correctness
- freshness timestamp presence
- separation of fact from inference
- usefulness to a human reviewer
- competitor comparison completeness

### Runtime

Measure:

- local generation latency
- peak memory usage
- malformed-output retry rate
- tool failure handling
- reproducibility with a fixed seed/configuration

## 9. Phased implementation plan

### Phase 0 — scope and data policy

Acceptance:

- product, ICP, channel, claims, and data policy are documented
- no private or paid data is required
- source provenance schema exists

Verify: human review of this scope.

### Phase 1 — structured baseline without fine-tuning

Acceptance:

- product and prospect records load successfully
- a deterministic positioning brief is produced
- a base model produces valid structured output
- baseline outputs are saved for comparison

Verify: unit tests and manual review of 10 examples.

### Phase 2 — evidence and research tools

Acceptance:

- collected documents retain source URL and timestamp
- the system can retrieve supporting excerpts
- unsupported claims are flagged
- scraping respects allowlists, rate limits, and source policy

Verify: fixture-based collector tests and citation review.

### Phase 3 — outreach dataset and LoRA adapter

Acceptance:

- reviewed train/validation/test split exists
- no prospect appears across conflicting splits
- adapter trains in Colab
- base-versus-adapter evaluation is reproducible

Verify: training log, held-out metrics, and manual comparison.

### Phase 4 — campaign evaluator

Acceptance:

- rubric is encoded
- evaluator flags deliberately inserted errors
- evaluator outputs structured scores and reasons

Verify: human-rated test set and agreement report.

### Phase 5 — agent orchestration

Acceptance:

- research → positioning → outreach → evaluation → revision works end to end
- tool errors are explicit
- generated drafts require human approval

Verify: end-to-end tests with mocked source data and manual demo.

### Phase 6 — local serving and interview packaging

Acceptance:

- local CLI or FastAPI endpoint serves the adapter
- README explains setup and limitations
- architecture diagram and evaluation report are complete
- a five-minute demo is repeatable

Verify: clean-environment run and interview rehearsal.

## 10. Proposed project structure

```text
src/
  data/             collection, normalization, provenance
  schemas/          product, prospect, evidence, campaign models
  research/         retrieval and positioning tools
  outreach/         prompts, adapter loading, generation
  evaluation/       rubric, metrics, regression checks
  runtime/          orchestration and local API
tests/              unit and integration tests
notebooks/          Colab setup and fine-tuning experiments
data/               gitignored local data only
results/            evaluation reports and samples
docs/               architecture, interview notes, decisions
```

## 11. Proposed commands

These commands become authoritative after the implementation stack is
approved:

```powershell
python -m pytest -q
python -m src.data.collect --config configs/sources.json
python -m src.research.position --input data/prospects/example.json
python -m src.outreach.generate --input data/prospects/example.json
python -m src.evaluation.run --split test
python -m src.runtime.local_api
```

No new dependency should be added without approval. The likely stack is
Python, NumPy/pandas, Pydantic, scikit-learn, Transformers, PEFT, TRL,
FastAPI, pytest, and a selected permitted source-extraction library.

## 12. Boundaries

### Always do

- keep product claims separate from model-generated language
- attach source URLs and timestamps to research evidence
- validate every structured model output
- keep human approval before outreach is sent
- run tests before committing
- record data provenance and evaluation configuration
- store secrets in `.env`, never in notebooks or source files
- report failures and uncertainty explicitly

### Ask first

- adding dependencies
- changing the base model or license
- collecting a new source domain
- storing personal or CRM data
- adding automatic email sending
- changing the evaluation rubric
- changing the project’s target user or channel
- moving from local serving to a paid hosted service

### Never do

- bypass login, paywalls, CAPTCHAs, or access controls
- scrape private pages or unnecessary personal data
- send automated outreach without human approval
- fabricate competitor facts, customer feedback, or product claims
- commit tokens, credentials, private datasets, or unreviewed customer data
- report synthetic examples as real business outcomes
- remove failing tests to make the model look better

## 13. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Too little high-quality training data | Start with prompting; fine-tune only one adapter after review |
| Model invents prospect facts | Require source-backed evidence fields and claim validation |
| Scraping breaks or violates policy | Use an allowlist, rate limits, caching, and source review |
| 270M model quality is insufficient | Benchmark a larger permitted model before expanding scope |
| Evaluator praises every draft | Insert known flaws and compare against human ratings |
| Demo becomes too broad | Keep one product, one ICP, and one channel |
| Results cannot be defended | Save prompts, versions, seeds, splits, sources, and reports |

## 14. Project deliverables

The finished project must include:

- a reproducible repository
- architecture diagram
- local inference demo
- one trained outreach adapter
- baseline-versus-adapter evaluation
- campaign-quality rubric and report
- source-backed research example
- failure analysis and limitations
- short README with setup and commands
- short project walkthrough

## 15. Open questions for approval

1. What hypothetical product should the demonstration sell?
2. Which single ICP should be used first?
3. Should the first channel remain B2B email?
4. Which model license and model size are acceptable?
5. Which public source domains are in scope for the research collector?
6. What minimum number of reviewed outreach examples can we create?

Implementation should not begin until these questions are answered and this
scope is approved.
