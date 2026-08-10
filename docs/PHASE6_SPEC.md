# Phase 6: Reviewed Dataset and One Outreach Adapter

## Objective

Create a small, reviewable, leakage-safe outreach training pilot and prepare
one LoRA/QLoRA adapter that can be compared with the Phase 5 prompt-only base
baseline. The adapter must improve defined outreach behavior without weakening
approved-claim or evidence support.

## V2 quality-correction slice

The technical pilot proved compatibility but did not pass semantic review. The
next adapter therefore uses an additive v2 contract; the v1 pilot remains
unchanged and reproducible.

### Grounded output contract

- `generation_status` is `drafted`, `needs_more_evidence`, `disqualified`, or
  `opted_out`.
- A drafted output contains a one-to-six-word subject and a 25-to-150-word
  body. Executive first-touch examples target 50-to-100 body words.
- Every body sentence appears exactly once in `support_map` and has one role:
  `prospect_fact`, `product_claim`, `hypothesis`, or `cta`.
- Every support-map entry contains exactly one grammatical sentence. CTA
  entries also declare `interest_question` or `approved_offer`; approved offers
  require a corresponding approved claim. Every CTA references an approved
  product claim, including an interest question.
- Prospect facts require evidence IDs; product claims require approved claim
  IDs. A sentence cannot combine claim and evidence IDs unless a future
  explicit relation contract approves that combination.
- A draft contains exactly one low-friction CTA. Offers, meetings, audits,
  trials, samples, or benchmarks cannot be mentioned unless their availability
  is represented by an approved claim.
- Hypotheses remain questions or use uncertainty language. They are never
  presented as known prospect conditions.
- Non-draft statuses contain no subject, body, support map, or sendable CTA and
  require an uncertainty note explaining the abstention.
- Global claim/evidence arrays are not generated. Reporting may derive them
  from `support_map`.

### Hard gates

All hard gates must pass before human scoring:

1. strict contract and exact body/support-map coverage;
2. approved claim and evidence identifiers only;
3. sentence-level citation precision and no unused citations;
4. support for every factual prospect and product sentence;
5. no unsupported claim/evidence combinations;
6. explicit uncertainty for hypotheses;
7. exactly one truthful, low-friction CTA;
8. safe abstention for insufficient evidence, disqualification, and opt-out;
9. configured subject and body bounds.

Semantic support is fail-closed: each factual support-map entry requires an
explicit reviewer/evaluator verdict. Every sentence, including hypotheses and
CTAs, requires an exact positive verdict snapshot covering its assigned role,
CTA kind, claim IDs, evidence IDs, and offer semantics. Identifier existence
alone is not treated as proof that a source supports the wording.

V2 content hashes normalize Unicode to NFC. The v1 digest remains byte-for-byte
unchanged so existing pilot rows and artifacts continue to validate.

### Human rubric and adapter acceptance

After hard gates pass, reviewers score personalization, grounding, clarity,
differentiation, CTA quality, and brand fit from 1 to 5. Adapter quality is
accepted only with at least 95% valid structured output, zero unsupported
claims/false citations/unsafe actions, no held-out hard-gate regression, a
blind average of at least 4/5 with no dimension below 3, measurable improvement
over the base model, and a separate untouched adversarial set.

### Dataset expansion sequence

Freeze a 60-to-100-case benchmark first. Then create and manually review a
balanced 100-row first-party slice before expanding toward 600-to-1,000 rows.
External synthetic rows remain auxiliary, attributed, and at or below 20% of
training tokens until an ablation proves benefit. Dataset generation does not
start in this contract slice.

### Frozen benchmark candidate

The first v2 benchmark candidate contains 60 controlled synthetic cases. It is
evaluation data only and must never be copied, paraphrased, or selected into a
training or validation split. Controlled synthetic inputs are appropriate here
because their claims, evidence, conflicts, stale dates, disqualification
signals, and opt-out state can have exact truth after manual review. They do
not establish real-world response or conversion performance.

Coverage is fixed at five product categories, five ICP patterns, five role
tiers, five evidence conditions, and both initial and follow-up outreach. The
status balance is 30 `drafted`, 15 `needs_more_evidence`, 8 `disqualified`, and
7 `opted_out` cases. Fifteen cases form a separately marked, untouched
adversarial subset. Remaining safety cases retain classification tags without
being counted in that protected subset.

Each case stores only input facts and expected invariants; no gold email prose
is included. Runners must use the typed prompt-input projection, which excludes
expected status, protected-set membership, adversarial tags, identity groups,
hashes, and reviewer metadata. Company and prospect identities are unique;
product, company, and prospect groups are disjoint from the v1 pilot, and case
IDs are disjoint from the Phase 1 benchmark.

Draft cases list `acceptable_claim_ids`, not one exact required claim. A passing
draft must cite at least one claim in that set; choosing another listed approved
claim is not a failure. `required_evidence_ids` remain exact because each draft
has one reviewed domain-relevant personalization anchor. Product categories use
their natural reporting, security, engineering, support, and revenue-operations
role ladders and distinct uncertain pain hypotheses.

The protected set contains ten drafted discipline traps and five conflicting-
evidence abstention cases. Five drafted traps include controlled synthetic
personal detail that must not appear in outreach, alongside product evidence
and prospect-side pilot language that does not authorize a product offer.

The corrected benchmark is frozen with user-authorized remediation provenance
and is evaluation-ready. All case review states, reviewer provenance, the
freeze timestamp, case hashes, and the manifest hash were regenerated together.
Any later content change invalidates the hashes and requires a new benchmark
version and review.

## Scope decisions

- The first pilot uses reviewed synthetic examples only. Public datasets remain
  disabled until their license, permitted use, and privacy posture are recorded.
- Training examples store provenance, generation method, reviewer status, and
  quality dimensions. Teacher-generated text is never accepted as truth solely
  because a model produced it.
- Product, company, and prospect identities are split groups. No identity may
  occur across train, validation, or held-out evaluation partitions.
- Phase 1's nine-case benchmark remains held out. It is evaluation data, not
  training data.
- Model weights and adapters remain outside Git in private Colab/Drive storage;
  only immutable revisions, configuration, hashes, and reviewed reports may be
  imported locally.
- Use the existing standard library and Pydantic contracts first. Adding
  `datasets`, `trl`, or another training dependency requires a separate review
  and approval.

## Dataset record contract

Every example must include:

- stable example ID and split;
- product, company, and prospect identity groups;
- source kind and source reference;
- license basis and license URL or an explicit synthetic basis;
- generation method;
- reviewer status and reviewer reference;
- quality dimensions for relevance, clarity, differentiation, credibility,
  CTA quality, and brand fit;
- approved claim IDs and personalization evidence IDs;
- structured target output or an explicit rejection reason.

Pending, rejected, malformed, duplicate, or unsupported examples cannot enter
the training split.

## Slice plan

### Slice 1: Contracts and audit validator

**Acceptance:** A reviewed synthetic pilot validates; missing provenance,
duplicate IDs, duplicate content, cross-split identity overlap, pending review,
and unsupported claim/evidence references fail loudly.

### Slice 2: Pilot manifest and split report

**Acceptance:** The pilot covers multiple products and ICP patterns, excludes
the Phase 1 held-out cases, and produces a deterministic split/audit report.

### Slice 3: Colab training scaffold

**Acceptance:** The notebook loads only the validated training split, captures
the exact configuration and base revision, performs bounded LoRA/QLoRA training,
and saves the adapter outside Git with a hash and revision record.

### Slice 4: Base-versus-adapter evaluation handoff

**Acceptance:** The adapter output uses the Phase 5 contract, is evaluated on
the unchanged held-out benchmark, and reports quality change plus factuality
and approved-claim regressions.

## Risks and controls

| Risk | Control |
| --- | --- |
| Training/evaluation leakage | Group-disjoint product, company, and prospect splits; held-out case exclusion. |
| Unreviewed teacher text becomes truth | Required reviewer status and quality labels; rejected/pending records are excluded. |
| Unclear data rights | Synthetic-only pilot until license evidence is recorded. |
| Adapter improves style but invents claims | Reuse Phase 5 deterministic claim/evidence gates as hard evaluation checks. |
| Colab session or GPU failure | Persist configuration and failure records; keep local validator and test-double path. |
| Artifact or credential leakage | Ignore model outputs/weights and keep only reviewed metadata in Git. |
