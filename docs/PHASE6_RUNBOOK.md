# Phase 6 Adapter Evaluation Runbook

## V2 quality-gate evaluation

The frozen 60-case benchmark is evaluated with the dedicated
`notebooks/phase6_v2_evaluation.ipynb` notebook. This notebook is
evaluation-only: it does not train or modify the saved adapter, and it does not
run the superseded nine-case pilot evaluation.

1. Open the notebook directly in Colab from the repository branch:
   [Open Phase 6 v2 evaluation in Colab](https://colab.research.google.com/github/muzzary/GTM-Agent/blob/codex/phase-6-reviewed-adapter/notebooks/phase6_v2_evaluation.ipynb).
2. Select **Runtime > Change runtime type > GPU**.
3. Run every cell from top to bottom. Approve Google Drive access when asked.
4. Confirm the setup output reports 60 cases and the expected adapter ID and
   revision.
5. Let the base-model cell finish all 60 requests. It saves its report before
   releasing the model from GPU memory.
6. Run the adapter cell. It evaluates the same 60 prompts and writes the final
   comparison.

Each run creates a timestamped private Drive directory under
`MyDrive/gtm-agent-phase6/evaluation-v2-<timestamp>/` containing:

- `phase6-v2-base-report.json`;
- `phase6-v2-adapter-report.json`; and
- `phase6-v2-comparison.json`.

Download those three files after the run. Do not upload model weights or the
adapter directory. The reports preserve bounded invalid-output excerpts for
diagnosis and use zero retries, so malformed output is a visible failed case.

### Reading the automated result

- `inconclusive` means the adapter produced fewer than 95% valid outputs or
  failed at least one deterministic case gate.
- `pending_semantic_review` means every adapter case passed deterministic
  structure, expected-status, citation-ID, required-evidence, and CTA gates.
- `accepted` remains false in both cases. Sentence support, personalization,
  differentiation, CTA quality, and brand fit require the separate blind
  semantic review before the Phase 6 quality gate can be accepted.

The prompt is built exclusively from the typed benchmark projection. Expected
status, acceptable and required output IDs, adversarial tags, protected-set
membership, hashes, identity groups, and reviewer metadata are withheld from
the model.

## V2 training run

Open `notebooks/phase6_outreach_adapter_v2.ipynb` in a private Colab GPU
runtime. It consumes `configs/phase6/training-v2.json`,
`configs/phase6/dataset-v2.json`, and `configs/phase6/benchmark-v2.json`.
Before loading the training model, it validates the reviewed
`DatasetManifestV2` with `validate_dataset_v2` and asserts a passing audit with
100 train rows and 24 validation rows.

The notebook runs three configured epochs with gradient accumulation and prints
mean `train_loss` and `validation_loss` after each epoch. It saves the adapter,
tokenizer, and `adapter-metadata.json` under the private Drive path
`MyDrive/gtm-agent-phase6/gtm-agent-outreach-v2/`.

After training, run `notebooks/phase6_v2_evaluation.ipynb`. That notebook
evaluates the saved adapter against the unchanged frozen v2 benchmark and
writes the base, adapter, and comparison reports to private Drive.

## Legacy technical-pilot evaluation

Phase 6 evaluates the saved LoRA adapter against the unchanged Phase 1/5
benchmark. The benchmark is never used for training. The Colab notebook runs
the pinned base model and adapter with the same prompts, generation settings,
and deterministic seed, then writes both reports and a comparison report to
private Google Drive.

### Legacy Colab evaluation

1. Open `notebooks/phase6_outreach_adapter.ipynb` in Colab and select a GPU.
2. Run the cells through adapter training and confirm the adapter metadata is
   present.
3. Set `APPROVED_MODEL_ID` and `APPROVED_MODEL_REVISION` to the reviewed
   Qwen model ID and 40-character revision already recorded in the notebook.
4. Run the evaluation cell. It loads the pinned base model, evaluates all nine
   unchanged benchmark cases, reloads the saved adapter on the same base
   revision, and evaluates the same cases again.
5. Confirm these private Drive artifacts are written:

   - `base-report.json`
   - `adapter-report.json`
   - `comparison.json`

The evaluation cell uses zero retries. Invalid model output becomes an explicit
failed case; it is never converted into a successful result. Failed cases keep
only a bounded raw-output excerpt for diagnosis. The selected Qwen Instruct
revision is already non-thinking-only; output normalization is not assumed.

### Legacy local validation

Download the two reports and `adapter-metadata.json` from Drive. Keep them in
an ignored local directory, then run:

```powershell
.\.venv\Scripts\python.exe -m src.evaluation.validate_phase6_comparison `
  "results/phase6/base-report.json" `
  "results/phase6/adapter-report.json" `
  "results/phase6/adapter-metadata.json" `
  --manifest "configs/phase1/benchmark.json" `
  --output "results/phase6/comparison.json"
```

The command fails closed unless the reports use the same benchmark cases and
generation settings, the adapter uses the recorded base revision, metadata
matches the adapter report, and the report remains within the size limit.

## Acceptance review

Phase 6 has two separate dispositions:

- **Technical pilot:** successful when training, artifact hashing, adapter
  loading, and deterministic base/adapter evaluation complete without
  structural or identifier regressions.
- **Quality gate:** accepted only after manual semantic review confirms useful,
  grounded outreach quality. Machine `accepted: true` does not override this
  review.

The deterministic report must show:

- at least the benchmark's 90% valid structured-output rate;
- zero unsupported adapter claim IDs;
- zero unresolved adapter evidence IDs;
- no per-case quality regressions versus the base report; and
- a quality result of `improved` or `unchanged`.

A run below the valid-output threshold is `inconclusive` and cannot be
accepted, even when both base and adapter fail in the same way.

Then manually compare representative base and adapter emails for relevance,
clarity, differentiation, credibility, CTA quality, and brand fit. Do not
accept the adapter based on style alone if factuality or approved-claim gates
regress.

## Recorded pilot disposition

The reviewed pilot completed 9/9 valid cases for both base and adapter, with no
unknown claim/evidence IDs and no identifier-level regressions. This marks the
technical pilot successful.

The semantic review did not accept outreach quality. It found unsupported fact
combinations, citations that were listed but not used, generic product copy,
and missing CTAs. The adapter was unchanged versus the base model. See
[`PHASE6_DATASET_AND_RUBRIC_RESEARCH.md`](PHASE6_DATASET_AND_RUBRIC_RESEARCH.md)
for the proposed data and rubric correction.
