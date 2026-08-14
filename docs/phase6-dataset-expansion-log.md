# Phase 6 dataset expansion log

## Calibration and expansion

- Expanded the deterministic candidate from 124 to 350 rows with the approved
  train and validation status counts.
- Calibrated one-, two-, and three-evidence buckets against the benchmark's
  computed one-item drafted share of 55.6 percent. Zero-evidence rows remain
  needs-more-evidence only.
- Scaled the controlled diversity pools and contrastive pairs to 40 pairs.
- Regenerated the candidate, review record, reviewed manifest, and review sheet
  in dependency order. All 350 review entries are approved.

## Training configuration

Set `epochs` to 5. With 300 train rows and gradient accumulation of 4, this is
75 optimizer steps per epoch and 375 steps total. Drafting first appeared near
step 150 in run 3, so 375 steps provides margin while keeping the run near two
hours rather than five.

## Verification

- `uv run pytest -q --basetemp=.tmp/pytest-codex`: 319 passed.
- `uv run ruff check .`: passed.
- Candidate hash: `2792972aecc2ecb1597da5b8dfd40b37e775818f22880662cbc4ae0f61a1736f`.
- Reviewed manifest hash: `1c3f6dfe5d22c566a6cb92f44bf4ae10634446ed33328baffbc95824e5908e2f`.
