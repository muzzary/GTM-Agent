# Phase 6 Adapter Evaluation Runbook

Phase 6 evaluates the saved LoRA adapter against the unchanged Phase 1/5
benchmark. The benchmark is never used for training. The Colab notebook runs
the pinned base model and adapter with the same prompts, generation settings,
and deterministic seed, then writes both reports and a comparison report to
private Google Drive.

## Colab evaluation

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
failed case; it is never converted into a successful result.

## Local validation

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

The deterministic report must show:

- zero unsupported adapter claim IDs;
- zero unresolved adapter evidence IDs;
- no per-case quality regressions versus the base report; and
- a quality result of `improved` or `unchanged`.

Then manually compare representative base and adapter emails for relevance,
clarity, differentiation, credibility, CTA quality, and brand fit. Do not
accept the adapter based on style alone if factuality or approved-claim gates
regress.
