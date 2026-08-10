# Phase 6 v2 Evaluation Build Log

## 2026-08-11: Evaluation path mismatch

- **Issue:** The existing adapter notebook evaluates only the legacy nine-case
  Phase 1/5 benchmark and old output schema.
- **Risk:** Reusing it would not evaluate the saved adapter against the frozen
  60-case grounded-output quality gate.
- **Resolution:** Add a separate evaluation-only runner and Colab notebook. The
  training notebook and historical pilot reports remain unchanged.

## TDD RED baseline

- New tests initially failed because `src.evaluation.phase6_v2` and a
  structural-only grounded-output evaluator did not exist.
- The notebook handoff tests separately failed until the dedicated v2 notebook
  was added.

## First GREEN correction

- **Issue:** The first request ID used a hyphen disallowed by the existing
  inference-request contract.
- **Fix:** Use canonical `req_phase6v2caseNNNN` identifiers.
- **Issue:** Extracting structural checks dropped the semantic verdict that
  detects an offer hidden behind an `interest_question` CTA label.
- **Fix:** Keep semantic offer detection in the reviewed evaluator while the
  structural evaluator explicitly makes no semantic-support claim.

## Formatting check

- Ruff found three long lines and one import-order issue. They were corrected
  mechanically without changing behavior.
- All 60 generated prompts are below the 12,000-character request limit; the
  observed maximum is 3,012 characters.

## Safety disposition

- The model receives only the typed prompt projection, never benchmark labels
  or protected-set metadata.
- Failed parses are recorded once with a bounded excerpt and no retry.
- Automated comparison cannot accept the quality gate. It can only report
  `inconclusive` or `pending_semantic_review`.
- Actual model evaluation remains pending execution on the user's private
  Colab GPU and saved Drive adapter.

## Pre-commit review corrections

- Bound external raw-output excerpts before report validation so one oversized
  diagnostic cannot abort the 60-case run.
- Reject duplicate report case/request IDs, invalid comparison thresholds, and
  adapter-labeled base reports.
- Catch generation-boundary failures only; evaluator programming errors now
  fail loudly instead of being mislabeled as model failures.
- Replaced the contradictory short, CTA-free JSON example with balanced draft
  and non-draft shape examples. The draft example satisfies the configured
  length and CTA structure while using explicit placeholder IDs.

## Verification

- Focused evaluation runner, notebook, and quality tests: 39 passed.
- Complete Phase 6 test selection: 84 passed.
- Full backend regression suite: 240 passed.
- Repository-wide Ruff and diff checks: clean, apart from known warnings for
  inaccessible pre-existing `.tmp/pytest-*` directories.
- Five-axis self-review: reviewed, clean after the corrections above.
