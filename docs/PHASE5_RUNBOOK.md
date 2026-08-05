# Phase 5 Baseline Runbook

Phase 5 evaluates prompt-only outreach before any adapter is used. The local
harness does not load model weights or call a network endpoint. A Colab adapter
must return the existing validated `InferenceResponse` contract; unavailable
inference is recorded as a failed attempt and retried at most once.

## Automated verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
```

The Phase 5 tests cover deterministic prompt construction, injection-resistant
context boundaries, approved-claim and evidence-ID checks, request/model
matching, retry limits, complete attempt traces, report reproducibility, and
strict report JSON round trips.

## Baseline data contract

- `claims_used` may contain only the approved claim IDs for the benchmark case.
- `evidence_used` may contain only the deterministic evidence IDs shown in the
  prompt, such as `evidence-case-reporting-regulated-1`.
- `uncertainty_notes` records unresolved support; semantic factuality still
  requires human review.
- The base model revision is recorded and adapter fields remain empty for a
  prompt-only run.
- Prompts are represented in reports by SHA-256 digest; full prompts and model
  artifacts remain local generated data.

## Manual review

Inspect a saved `BaselineReport` under `results/` and confirm:

1. Every benchmark case has a validated output or an explicit failure.
2. Every case has at least one trace entry, including failed retries.
3. A successful response records model revision and latency.
4. Unsupported claim/evidence IDs make the case fail.
5. A failed Colab request produces a visible failure and never a fabricated
   successful output.

Reports are generated with `save_baseline_report(report, Path(...))` and loaded
with `load_baseline_report(path)`. Generated reports should remain ignored
unless a reviewed report is intentionally committed.
