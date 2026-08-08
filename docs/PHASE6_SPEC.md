# Phase 6: Reviewed Dataset and One Outreach Adapter

## Objective

Create a small, reviewable, leakage-safe outreach training pilot and prepare
one LoRA/QLoRA adapter that can be compared with the Phase 5 prompt-only base
baseline. The adapter must improve defined outreach behavior without weakening
approved-claim or evidence support.

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
