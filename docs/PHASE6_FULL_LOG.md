# Phase 6 Full Log: Grounded Outreach Adapter

Complete record of the Phase 6 fine-tuning effort — setup, data, every training
run, every defect found, and the open questions. Written 2026-08-17.

**Status: Phase 6 quality gate NOT met.** Best adapter scores 45/60 on the frozen
benchmark against a 27/60 base. The gate requires 55/60.

---

## 1. Objective

Produce one LoRA adapter that improves grounded B2B outreach behaviour over the
prompt-only base model, without weakening approved-claim or evidence support.

The model's job is a decision first and a writing task second. For each prospect
it must choose exactly one of:

| Status | Meaning |
| --- | --- |
| `drafted` | Enough approved evidence exists — write the email |
| `needs_more_evidence` | Evidence is thin, stale, conflicting or absent — abstain |
| `disqualified` | Prospect is structurally not a fit — abstain |
| `opted_out` | Consent withdrawn or an explicit stop request — abstain |

Choosing `drafted` when the prospect opted out is the worst possible failure, so
abstention discipline is safety-critical, not merely a quality dimension.

---

## 2. Base model and training setup

| Item | Value |
| --- | --- |
| Base model | `Qwen/Qwen3-4B-Instruct-2507` |
| Pinned revision | `cdbee75f17c01a7cc42f958dc650907174af0554` |
| Parameters | 4,055,498,240 |
| Quantisation | 4-bit NF4 via bitsandbytes, double quant, fp16 compute |
| Adaptation | LoRA, rank 16, alpha 32, dropout 0.05, `target_modules: all-linear` |
| Trainable params | 33,030,144 (0.81% of total) |
| Max sequence length | 1536 |
| Learning rate | 1e-4, AdamW |
| Gradient accumulation | 4 |
| Seed | 42 |
| Generation at eval | greedy (`do_sample=False`), `max_new_tokens=768`, seed 42 |

Config lives in `configs/phase6/training-v2.json`. The v1 config
(`configs/phase6/training.json`) is deliberately untouched so the original pilot
stays reproducible.

**Hardware note.** 4-bit training requires CUDA compute capability ≥ 7.0.
Kaggle sometimes assigns a Tesla P100 (sm_60), on which the bitsandbytes kernel
dies. Use T4 or newer. The Kaggle preflight now rejects incompatible GPUs.

### Loss masking

Loss is computed **only over the assistant response**, not the prompt. Prompts run
1,000+ tokens against targets of a few hundred; unmasked training would spend most
of the gradient teaching the model to reproduce its own prompt. Implementation:

```python
prompt_ids  = apply_chat_template(build_chat_messages(prompt), add_generation_prompt=True)
input_ids   = apply_chat_template(build_chat_messages(prompt, target), add_generation_prompt=False)
assert torch.equal(prompt_ids[0], input_ids[0, :prompt_length])   # per example
labels = input_ids.clone()
labels[:, :prompt_length] = -100
```

The prefix assertion runs on **every** example, so template drift or truncation
fails loudly rather than silently training on prompt tokens.

---

## 3. Output contract

Model output is a single JSON object validated by `GroundedOutreachOutput`:

- `generation_status` — one of the four statuses above
- `subject` — 1–6 words for drafts, empty otherwise
- `body` — 25–150 words for drafts, empty otherwise
- `support_map` — one entry per body sentence, in order
- `uncertainty_notes` — non-empty for every non-draft

Hard rules enforced deterministically:

- `body` must equal `" ".join(entry.sentence for entry in support_map)` exactly
- each entry carries a role: `prospect_fact`, `product_claim`, `hypothesis`, `cta`
- `prospect_fact` requires evidence IDs; `product_claim` requires approved claim IDs
- a sentence may not carry both claim IDs and evidence IDs
- exactly one CTA, which must cite an approved claim
- hypotheses stay questions or use uncertainty language
- non-drafts carry empty subject/body/support_map plus an uncertainty note

---

## 4. Benchmarks

### 4.1 Outreach benchmark — frozen, 60 cases

`configs/phase6/benchmark-v2.json`, manifest hash
`c9b3445c2613fda0b5b036f1a7052d84797f505ac823ca58519f264f46e1c123`.

| Expected status | Cases |
| --- | ---: |
| `drafted` | 30 |
| `needs_more_evidence` | 15 |
| `disqualified` | 8 |
| `opted_out` | 7 |

15 cases form a protected adversarial subset (drafted discipline traps,
conflicting-evidence abstentions, invasive-personalisation baits). Coverage spans
5 product categories, 5 ICP patterns, 5 role tiers, 5 evidence conditions, and
both initial and follow-up outreach. Cases store only inputs and expected
invariants — no gold email prose. Runners see a typed prompt projection that
excludes expected status, protected-set membership, hashes, and reviewer fields.

### 4.2 CRM agent benchmark — frozen, 40 cases

`configs/phase6/crm-benchmark.json`. Built but **never used** — no CRM training
data or adapter exists yet.

| Category | Cases | | Category | Cases |
| --- | ---: | --- | --- | ---: |
| read_lookup | 8 | | refusal | 6 |
| approval_required_write | 7 | | idempotent_replay | 4 |
| approved_write | 5 | | multi_step | 4 |
| clarification | 6 | | **protected adversarial** | **12** |

Its distinguishing property: **expectations are verified by execution.** Every
expected tool call is run through the real `ControlledAgentRuntime` against a
seeded `CrmService`, so a case whose expected call cannot actually execute fails
the audit. Adversarial tags cover fabricated tools, approval bypass, injected
instructions inside CRM record data, missing arguments, out-of-scope requests,
and idempotency violations.

---

## 5. Dataset

`configs/phase6/dataset-v2.json` — currently **350 rows**, 300 train / 50
validation. Produced by a deterministic builder
(`src/evaluation/build_phase6_dataset_v2.py`) through a three-artifact pipeline:

```
build_phase6_dataset_v2.py
   -> dataset-v2.candidate.json   (rows marked pending review)
   -> dataset-v2.review.json      (per-row approval + reviewer provenance)
   -> dataset-v2.json             (strict DatasetManifestV2, training-ready)
```

The candidate step exists because `TrainingExampleV2` refuses a train-split row
whose review status is not `reviewed` — pending rows are literally unconstructible
in the final shape, which is the schema doing its job.

### Current composition

| Split | drafted | needs_more_evidence | disqualified | opted_out |
| --- | ---: | ---: | ---: | ---: |
| train | 165 | 60 | 40 | 35 |
| validation | 27 | 10 | 7 | 6 |

Evidence-count calibration, matched to the benchmark's dominant bucket:

| Evidence items | Rows | Drafted share |
| ---: | ---: | ---: |
| 0 | 13 | 0% (abstain only — genuine, zero evidence cannot support a draft) |
| 1 | 170 | 57% |
| 2 | 85 | 55% |
| 3 | 82 | 57% |

Benchmark's 1-item bucket is 56% drafted. All non-zero buckets now sit at the same
rate, so evidence count carries no information about the label.

40 contrastive pairs (80 rows). Both members share byte-identical context evidence
and differ only by the deciding signal — an added opt-out record, an added
disqualifier, the same evidence aged past 12 months, or a second contradicting
item.

Quality invariants asserted in the builder and tests: no evidence ID cited twice
in a row; no claim ID more than twice; bodies 40–95 words with 3–6 support
entries; a prose ban list preventing sentences from announcing their own sourcing;
abstention rationales bound to the row's actual evidence condition; 310 distinct
companies; 40 target roles; 8 products; 153 distinct rationales; identity groups
disjoint from the frozen benchmark.

### Dataset evolution

| Version | Rows | What changed | Outcome |
| --- | ---: | --- | --- |
| v1 pilot | 6 (3 train) | Original sendable-email format | Adapter learned the wrong contract |
| v2 initial | 124 | Structured contract, 40/24/18/18 | Mode collapse to abstain-only |
| v2 rebalanced | 124 | 65/15/10/10 toward drafting | **Best result: 45/60** |
| v2 shortcut-fixed | 124 | Broke evidence-count shortcut | 41/60 |
| v2 pairs-repaired | 124 | Real contrastive pairs, benchmark-style evidence text | (folded into next) |
| v2 expanded | 350 | Calibrated buckets, 40 pairs | 36/60 |

---

## 6. Training runs

| # | Data | Epochs / steps | Evaluated | Valid | **Deterministic** | drafted | abstentions |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: |
| — | base model, no adapter | — | — | 46/60 | **27/60** | 24/30 | 3/30 |
| 0 | v1 pilot, 3 rows | — | final | 49/60 | 29/60 | — | — |
| 1 | 124, abstain-heavy | 3 / 39 | final | 60/60 | 29/60 | 0/30 | 29/30 |
| 2 | 124 rebalanced | 4 / 100 | **lost** | — | — | — | — |
| 3 | 124 rebalanced | 7 / 175 | epoch 7 | 59/60 | **45/60** | 16/30 | 29/30 |
| 4 | 124 shortcut-fixed | 8 / 200 | epoch 8 | 59/60 | 41/60 | 17/30 | 24/30 |
| 5 | 350 calibrated | 5 / 375 | none | — | — | 0 drafts ever | — |
| 6 | 350 calibrated | 8 / 600 | epoch 7 | 60/60 | 36/60 | 6/30 | **30/30** |

### Run 1 — mode collapse

Trained on 124 rows that were 60% abstention, with 39 optimizer steps. The adapter
emitted **zero drafts across all 60 benchmark cases**. It learned abstention
perfectly (3/30 → 29/30) and destroyed drafting (24/30 → 0/30).

Cause: abstention targets are ~7× shorter than drafts (median 185–224 chars vs
1,524) and near-deterministic. "Always emit the abstention shape" was an immediate
near-zero-loss minimum covering 60% of examples, and 39 steps was not enough to
then learn the expensive mode. Training loss fell 0.83 → 0.29, which looked
healthy and was not — the validation split carried the same 60/40 skew, so it fell
in lockstep and could not reveal that an entire output mode had died.

**This is why the per-epoch mode-collapse probe was built.**

### Run 3 — best result, 45/60

Rebalanced to 65% drafted. Drafting first appeared at epoch 4, relapsed entirely at
epoch 5, recovered at 6, reached 12/12 on the probe at epoch 7. The GPU quota ran
out at epoch 7; the per-epoch checkpoint made the run salvageable.

Failure analysis of the 15 misses: 10 were drafts it abstained on (7 with strong
evidence), 3 were drafts that failed on contract slips, 1 unparseable, 1
over-draft. Protected adversarial 11/15 versus ordinary 34/45 — statistically
indistinguishable, meaning the residual was a fixable bias rather than a
benchmark-difficulty ceiling.

### Run 4 — 41/60, over-corrected

After breaking the evidence-count shortcut, the model swung to over-drafting: 27
drafts emitted versus run 3's 20, but only +1 correct draft, and protected
adversarial dropped 11/15 → 8/15. The single-evidence bucket had gone from 0%
drafted to 78%, versus the benchmark's 56% — direction fixed, magnitude wrong.

### Run 5 — never drafted

350 rows at 5 epochs = 375 optimizer steps, more than run 4's 200. Zero drafts at
any epoch. **Repetitions per example, not optimizer steps, govern when drafting
emerges.** It has appeared on the sixth pass in every run where it appeared at all.
Run 5 stopped at five.

### Run 6 — 36/60, and the finding that reframes the phase

Same data, 8 epochs. Drafting emerged at epoch 6 exactly as predicted; probe hit
12/12 at epochs 6 and 7, dipping to 10/12 at epoch 8 with validation loss rising,
so the epoch-7 checkpoint was evaluated.

Result: **all 30 abstention cases correct, 6 of 30 drafts correct.** It emitted 9
drafts against 30 expected, abstaining on 21 — 17 of which had strong evidence.

---

## 7. Issues encountered

### 7.1 Data design defects — the expensive category

| # | Defect | How it was found |
| --- | --- | --- |
| 1 | Diversity metrics gamed by templates plus an injected row number ("Row 002 is blocked because…", "Clearer path for recurring review 041") | Manual inspection of generated rows |
| 2 | 26 of 50 drafts cited the same evidence ID twice to pad to a word count, presenting one fact as several | Scripted audit |
| 3 | Body sentences announced their own sourcing ("Public evidence from X: The operations guide says…") | Reading the review sheet |
| 4 | Abstention rationales uncorrelated with the row's evidence — two rows claimed a "fourteen-month-old source" when evidence was ten days old; one claimed "no evidence found" on a row with two evidence items; seven paired `needs_more_evidence` with strong evidence, which the frozen benchmark contract explicitly forbids | Scripted audit against the schema's own rules |
| 5 | **Evidence count perfectly predicted the label** — 1 item → never drafted (0/25), 3 items → always drafted (48/48), while 25 of the benchmark's 30 drafts have exactly one evidence item | Cross-distribution audit after run 3 |
| 6 | **Contrastive pairs were not contrastive** — 0 of 15 shared a single piece of evidence; one pair contrasted "one fact" against "no facts", re-teaching the counting shortcut | Scripted pair check |
| 7 | Training evidence text format differed from the benchmark's | Length/format comparison |
| 8 | Stale evidence used only the year 2025; the benchmark's stale cases are 2024 | Year distribution audit |

Defects 1–4 each required a full dataset rebuild. The recurring lesson: **a
generator optimises whatever you measure, including things you never meant to
encode.** Criteria that count distinct strings are satisfiable by combinatorics;
criteria that bind output to input are not.

### 7.2 Code and pipeline defects

| Defect | Severity | Status |
| --- | --- | --- |
| Training tokenised with raw `tokenizer(...)` while evaluation used `apply_chat_template` — the adapter never saw the token format it was evaluated on | High | Fixed; shared helpers now guarantee parity |
| No v2 training path existed; the adapter was trained on 3 v1 sendable-email rows | High | Fixed |
| Evaluation notebook loaded the **v1** training config, resolving to the old `gtm-agent-outreach-pilot` adapter directory — which still existed, so the assert passed and it would have silently evaluated the wrong adapter | High | Fixed + identity guards added |
| `_validate_report_pair` did not compare prompt hashes, so a reused base report from before a prompt change would be silently accepted | High (we reuse base reports) | Fixed |
| Frozen CRM benchmark could not be loaded back from disk — persisted collections declared as tuples, and `StrictModel` will not coerce a JSON list. Tests compared serialised text and never exercised the load path | High | Fixed + on-disk load test added |
| Adapter fingerprint hashed every file in the directory including the previous epoch's metadata | Medium | Fixed |
| Validation loss left the model in eval mode; probe restored assumed rather than actual state | Medium | Fixed |
| Gradient accumulation divided by the configured step count even for a short final group | Medium | Fixed |
| Notebooks hardcoded `split_counts["train"] == 100`, breaking on dataset expansion | Low | Fixed — now asserts invariants |
| Review-sheet word ceiling broke CI after the dataset grew; the limit was duplicated between module and test | Low | Fixed — test imports the constant |

### 7.3 Infrastructure issues

- **Two training runs lost to disconnects** before any checkpoint existed. Fixed
  by per-epoch checkpointing into `run-NN/checkpoints/epoch-NN/`, with
  `adapter-metadata.json` written **last** as a completion marker so a partial
  write is identifiable. No atomic rename is relied on — Drive is a FUSE mount.
- **Colab GPU quota exhausted twice.** Mitigated by porting both training and
  evaluation to Kaggle, whose quota is independent. Kaggle committed runs execute
  server-side and survive a closed browser.
- **Stale PEFT import** after re-running `%pip install` in a live session produced
  `AttributeError: 'LoraConfig' object has no attribute 'velora_config'` —
  `peft.config` came from the preinstalled build while `peft.tuners.lora.bnb`
  loaded from the newly installed one. Fixed by a preflight comparing each
  package's installed metadata version against its imported `__version__`.
- **Kaggle assigned a Tesla P100** (sm_60), on which 4-bit kernels are
  unsupported; the kernel died two minutes in. Preflight now checks compute
  capability and names the remedy.
- Local test runs showed ~32 spurious `PermissionError` results because the shell
  cannot write to the system temp directory. This **masked a genuine CI failure**
  for several commits. Resolved by pointing pytest at a writable scratch dir with
  `--basetemp`.

---

## 8. What is proven, and what is not

### Established

- **Structured output is solved.** 46/60 → **60/60** valid. The JSON contract,
  including the exact `body == join(support_map)` constraint, is reliably learned.
- **Abstention is solved.** 3/30 → **30/30** across all three abstention modes in
  run 6. Opt-outs, disqualifications and insufficient evidence are handled
  correctly. This is the safety-critical half.
- **Drafting emerges on the sixth pass** over each example, in every run where it
  emerged at all — independent of optimizer-step count.
- **Validation loss is the wrong early-stopping signal** for this task. In run 3 it
  bottomed at epoch 5, which was a total relapse to zero drafts, while probe
  accuracy kept climbing to epoch 7.

### Open

- **Drafting does not generalise to the benchmark.** Run 6 scored 12/12 on the
  validation probe and 6/30 on benchmark drafts.
- **The validation probe is not a generalisation signal.** It draws from the same
  generator as training and shares every idiosyncrasy, so it measures style
  memorisation. It reported 12/12 while the benchmark reported 6/30, and it caused
  several runs to be read as healthy that were not.
- **A severe train/test input mismatch exists:**

  ```
  TRAIN: 0/586 evidence items use a placeholder company name
  BENCH: 70/70 evidence items use a placeholder company name
  ```

  Benchmark evidence reads *"Benchmark Company 001's operations handbook notes
  weekly regional scorecards."* Training evidence reads *"The Northwind Freight
  operations handbook assigns recurring workflow reviews…"*. The model has never
  seen a draft about a placeholder-named company. This was introduced by the very
  first dataset review, which banned placeholder names as templating — correct for
  the product, and it moved training away from the benchmark's input form.

  The base model drafts 24/30 on those same inputs, so naming alone does not
  prevent drafting. The hypothesis is that fine-tuning taught a conditional policy
  whose condition does not fire on benchmark inputs, leaving the most-reinforced
  fallback: abstain. **Unproven.**

- **Whether adapter capacity binds.** 33M trainable parameters currently carry
  drafting, three abstention modes, and an exact citation contract.

### The strategic tension

The benchmark tests on companies called "Benchmark Company 001"; production will
see "Northwind Freight". Tuning training until it scores well on placeholder-named
inputs may optimise a benchmark artifact rather than outreach quality. This is a
real fork and has not been decided.

---

## 9. Artifacts

| Artifact | Location |
| --- | --- |
| Best adapter (45/60) | Private Drive, run 3 epoch-7 checkpoint |
| Latest adapter (36/60) | Kaggle notebook output, `run/checkpoints/epoch-07`, revision `b568eb37…` |
| Outreach benchmark | `configs/phase6/benchmark-v2.json` (frozen) |
| CRM benchmark | `configs/phase6/crm-benchmark.json` (frozen, unused) |
| Training dataset | `configs/phase6/dataset-v2.json` |
| Training config | `configs/phase6/training-v2.json` |
| Colab notebooks | `notebooks/phase6_outreach_adapter_v2.ipynb`, `phase6_v2_evaluation.ipynb` |
| Kaggle notebooks | `notebooks/phase6_outreach_adapter_v2_kaggle.ipynb`, `phase6_v2_evaluation_kaggle.ipynb` |

Model weights never enter Git. Only immutable revisions, configuration, hashes and
reviewed reports are committed.

**Provenance weakness:** adapter metadata records `dataset_id` and
`dataset_version`, both unchanged across six materially different dataset builds.
Two adapters trained on different data therefore carry identical provenance.
`DatasetManifestV2` already computes a content hash; recording it is a tracked
follow-up.

---

## 10. Gate status

| Requirement | Target | Best actual |
| --- | --- | --- |
| Valid structured output | ≥ 95% | **100%** ✅ |
| Deterministic passes | ≥ 55/60 | 45/60 ❌ |
| Blind human review | ≥ 4/5 avg, none below 3 | not reached |
| Improvement over base | required | 27 → 45 ✅ |
| Untouched adversarial set | required | 15 protected cases ✅ |

The gate was lowered from 60/60 to 55/60 by explicit decision, with a full 60
still preferred. `accepted` remains a computed property that always returns
`False` — machine gates never accept Phase 6 quality; blind semantic review is a
separate, later step that has never been reached.

## 11. Options from here

1. **Mix both naming styles in training** so drafting does not depend on how a
   company is named. Removes a spurious sensitivity rather than teaching to the
   test. One rebuild plus one ~4h run.
2. **Bank run 3's 45/60**, document Phase 6 as a measured 27 → 45 improvement
   below its gate, and move to the CRM half, where a frozen 40-case benchmark
   already exists and nothing has been trained.
3. **Re-freeze the benchmark with realistic company names.** Arguably fixes a real
   benchmark defect, but invalidates every comparison in this log.
4. **Test the naming hypothesis cheaply** by running the base model and run 3's
   adapter over a few benchmark cases rewritten with realistic names, before
   committing more GPU time.

Independent of the choice, the probe should sample benchmark-style inputs rather
than the validation split, so future runs are readable.
