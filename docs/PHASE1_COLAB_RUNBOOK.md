# Phase 1 Colab Runbook

This is the manual gate for Phase 1. It runs real inference and a minimal QLoRA
training step on the GPU assigned by Google Colab. It does not expose Colab as
a web service.

## Prerequisites

- A Google account with Colab and Google Drive access.
- A Colab GPU runtime. CPU-only runs do not satisfy Phase 1.
- The public `codex/phase-1-colab-feasibility` branch available on GitHub.
- Enough private Google Drive space for benchmark reports and temporary smoke
  adapters.

The two initial candidates are public and do not require a Hugging Face token.
Both use model implementations built into the pinned Transformers release;
remote repository code remains disabled.

## Run the benchmark

1. Open
   [`notebooks/phase1_colab_feasibility.ipynb`](../notebooks/phase1_colab_feasibility.ipynb)
   in Google Colab.
2. Select **Runtime > Change runtime type > GPU**.
3. Run each cell in order.
4. Approve the Google Drive mount. Artifacts are written under
   `MyDrive/GTM-Agent/phase1/`.
5. Confirm `environment.json` records the repository revision, manifest hash,
   assigned GPU, CUDA, Python, PyTorch, and pinned library versions.
6. Let both candidate runs finish. Each candidate writes its report immediately;
   a later Colab disconnect therefore does not discard earlier results.
7. If a candidate fails, keep its generated `--failure.json` report. Do not
   rerun with changed versions or a different model revision.

## Review and select

Review representative valid and invalid outputs from each candidate report.
Rate each candidate from 1 to 5 across:

- relevance
- clarity
- differentiation
- credibility
- CTA quality
- brand fit

Enter the average ratings in `HUMAN_RUBRIC_AVERAGES` and run the recommendation
cell. A candidate is excluded unless it reaches at least 90% valid structured
outputs, uses zero unsupported claim IDs, and passes the QLoRA smoke test.

Set `APPROVED_MODEL_ID` only after reviewing the recommendation. If you override
the recommendation, document the reason in the comparison report.

## Export and validate a real result

Run the final notebook cell. It prints the bundle path, request ID, exact model
revision, and SHA-256 digest. Download that bundle to a local ignored directory,
for example `results/phase1/`, then validate it from the repository root:

```powershell
uv run python -m src.evaluation.validate_phase1_bundle `
  "results/phase1/inference-bundle--REQUEST_ID.json" `
  --request-id "REQUEST_ID" `
  --model-revision "MODEL_REVISION"
```

The validator prints only bundle identity metadata, not the generated email.

## Return for phase completion

Provide these artifacts or their relevant values for review:

- `environment.json`
- both candidate reports or explicit failure reports
- `candidate_comparison.json`
- the selected model ID and exact revision
- the generated bundle's request ID, revision, and validation result

Keep model weights, smoke adapters, generated result files, and any private
Drive paths out of Git. Clear notebook outputs before saving or sharing the
notebook. If neither candidate passes every hard gate, stop Phase 1 rather than
selecting the least-bad failure.
