# Phase 6 Benchmark Build Log

This log records recoverable issues encountered while creating the frozen
Phase 6 outreach benchmark, together with their diagnosis and resolution.

## 2026-08-10: Dataset test path lookup

- **Issue:** Initial repository inspection referenced
  `tests/test_training_dataset.py`, which does not exist.
- **Diagnosis:** The Phase 6 dataset coverage is split between
  `tests/test_phase6_dataset.py` and `tests/test_phase6_dataset_v2.py`.
- **Resolution:** Located the authoritative files with `rg --files` and used
  those paths for the benchmark design review. No source files were changed by
  the failed read.

## 2026-08-10: Global uv cache permission

- **Issue:** The first benchmark contract test run stopped before collection
  because the managed Windows environment denied access to uv's global cache.
- **Diagnosis:** This is a local cache-path permission problem, not a test,
  dependency, or benchmark failure.
- **Resolution:** Run verification with `UV_CACHE_DIR` set to the repository's
  ignored `.uv-cache` directory. No package versions or lockfiles are changed.

## 2026-08-10: Expected contract-test failure

- **Issue:** Benchmark tests failed collection because
  `src.evaluation.phase6_benchmark` did not exist.
- **Diagnosis:** This is the expected test-first RED state proving the tests
  exercise a new benchmark boundary rather than existing behavior.
- **Resolution:** Implement the minimal Phase 6 benchmark schema, loader, and
  auditor required by the contract tests.

## 2026-08-10: Fixture status mismatch and missing manifest

- **Issue:** Four contract tests failed after implementation.
- **Diagnosis:** Three failures came from the test factory pairing strong
  evidence with `needs_more_evidence`; one correctly reported that the frozen
  JSON manifest had not yet been created.
- **Resolution:** Make the factory produce all four status classes with valid
  evidence/status combinations, then create the manifest. Product identities
  may repeat across benchmark cases to measure multiple prospects for one
  product; company and prospect identities remain unique and all three identity
  kinds remain disjoint from training data.

## 2026-08-10: Negative fixture removed mandatory safety signals

- **Issue:** The missing-coverage test attempted to remove every adversarial
  tag, including the mandatory opt-out and disqualification signals.
- **Diagnosis:** Case-level safety validation correctly rejected the fixture
  before the manifest auditor could assess its adversarial-case count.
- **Resolution:** Keep one valid opt-out and one valid disqualification case,
  convert the other abstention fixtures to `needs_more_evidence`, and leave the
  total protected count below twelve.

## 2026-08-10: Premature review claim and label-exposure risk

- **Issue:** The generated candidate used completed reviewer metadata before
  user review, and a future runner could accidentally serialize expected
  labels into the model prompt.
- **Diagnosis:** Both weaken benchmark trust: the first overstates the
  artifact's lifecycle, while the second permits evaluation-label leakage.
- **Resolution:** Add explicit pending/frozen lifecycle fields, keep the first
  artifact pending until manual acceptance, and expose a typed prompt-input
  projection that omits expected status, adversarial tags, identities, hashes,
  and reviewer metadata. Rebalance to 30 drafts, 15 evidence abstentions, 8
  disqualifications, and 7 opt-outs.

## 2026-08-10: Mechanical patch context mismatch

- **Issue:** The first combined lifecycle patch did not apply.
- **Diagnosis:** The patch expected unwrapped scenario lines, but the file
  contained formatter-wrapped lines.
- **Resolution:** Confirm no partial changes were made, inspect the exact
  context, and apply smaller patches.

## 2026-08-10: Derived disqualification tag mismatch

- **Issue:** The rebalanced generator produced `disqualified_signal`, which is
  outside the benchmark tag contract.
- **Diagnosis:** A compact string transformation did not match the deliberately
  named `disqualification_signal` safety tag. The generator stopped before
  overwriting the previous JSON, whose old lifecycle fields then failed the new
  loader as expected.
- **Resolution:** Replace the transformation with an explicit status-to-signal
  mapping and regenerate the complete manifest.

## 2026-08-10: PowerShell glob and line wrapping

- **Issue:** The Phase 6 test command passed a wildcard literally to Pytest,
  and Ruff reported long lines in the new generator and auditor.
- **Diagnosis:** PowerShell did not expand the path pattern in this invocation;
  the Ruff findings are formatting-only and do not indicate behavior failures.
- **Resolution:** Select Phase 6 tests with Pytest's `-k phase6` filter and run
  the repository formatter on the new Python files before linting again.

### Formatter follow-up

- Ruff formatting resolved structural wrapping but intentionally left seven
  long string expressions unchanged. They were split into adjacent string
  segments without changing generated benchmark content.

## 2026-08-10: Nested prompt metadata exposure

- **Issue:** The typed prompt projection excluded top-level evaluation fields
  but reused full claim and evidence records, leaving nested content hashes,
  license fields, and source-reference metadata in the serialized prompt input.
- **Diagnosis:** These are not expected labels, but they are unnecessary model
  context and contradicted the documented minimal projection boundary.
- **Resolution:** Add prompt-only claim and evidence contracts containing only
  the approved IDs/text plus evidence URL and collection time, and strengthen
  the test to scan the complete nested payload.

### Projection cleanup

- The refactor left two dataset-record imports unused. Focused tests passed;
  Ruff identified the dead imports, which were removed without behavior change.

## 2026-08-10: Fresh-context adversarial review

The single-model adversarial review verified four gaps:

- exact `30/15/8/7` status and 15-case protected distributions were reported
  but not enforced;
- deleting stored hashes caused validators to generate replacements during
  load, bypassing artifact tamper detection;
- blocked identity checks omitted ICP groups;
- controlled-synthetic provenance was a builder convention rather than a case
  invariant.

All four findings were accepted for correction. The audit now enforces exact
distributions, the loader requires every persisted hash before validation,
blocked overlap includes ICP identity, and benchmark claims/evidence must use
the controlled first-party synthetic provenance boundary.

### Exact-count assertion follow-up

- One negative test still expected the superseded “fewer than 12” error text.
  The implementation correctly emitted the new “exactly 15” requirement; the
  assertion was updated to match the tightened contract.

## Final verification

- Focused benchmark tests: 15 passed.
- Complete Phase 6 test selection: 66 passed.
- Full backend regression suite: 222 passed.
- Repository-wide Ruff and diff checks: clean.
- Two consecutive deterministic builds produced the same file digest.
- The technical audit passes with no duplicate, coverage, provenance, or
  identity-overlap errors.
- Lifecycle remains `pending_review`; `evaluation_ready` remains false.

## 2026-08-10: Git index sandbox permission

- **Issue:** Git staging could not create `.git/index.lock` inside the managed
  sandbox.
- **Diagnosis:** Repository files are writable, but this session's default
  filesystem profile exposes `.git` read-only.
- **Resolution:** Retry only the explicit scoped `git add` operation with Git
  repository-write approval. No file content or history was altered by the
  failed staging attempt.

## 2026-08-10: Claude Opus 4.8 semantic review

- **Initial issue:** The first read-only Claude CLI request failed before model
  inference because the local OAuth session had expired. No tokens were used
  and no cost was incurred.
- **Resolution:** The user renewed Claude authentication. The same request was
  rerun with exact model `claude-opus-4-8`, maximum effort, read-only tools, no
  fallback, no session persistence, and a USD 15 cap.
- **Result:** Opus individually reviewed all 60 cases for USD 2.435928 and
  returned `APPROVE_WITH_FIXES`: 55 pass, 5 need case-specific corrections,
  with additional cross-case template, claim-selection, role, and adversarial
  coverage findings.
- **Verification:** Codex reproduced the five weak-evidence ambiguities, uniform
  role distribution, protected-case composition, and missing
  `invasive_personalization` coverage directly from the manifest.
- **Disposition:** Keep the benchmark `pending_review` and
  `evaluation_ready: false` until corrections and final re-review complete.

## 2026-08-10: Opus remediation RED baseline

- **Issue reproduced:** The correction tests fail against the old candidate:
  five weak signals are domain-irrelevant, exact claim selection is arbitrary,
  all products share one operations role ladder, the protected set contains
  only drafts, invasive personalization is absent, and shortcut wording is
  repeated.
- **Contract change:** Because the candidate is not frozen and has no evaluation
  consumer yet, replace `required_claim_ids` with `acceptable_claim_ids`.
  Drafts must cite at least one ID from this set; they are no longer forced to
  match one arbitrary claim.
- **External review:** Per user instruction, Claude Opus will not be rerun after
  these corrections.

### Corrected-builder verification

- The regenerated candidate passes all 20 focused benchmark tests.
- Ruff found one long reporting-disqualifier string; it was wrapped without
  changing generated content.

### Freeze RED baseline

- The corrected artifact still reported `evaluation_ready: false` because its
  lifecycle remained `pending_review`.
- The user authorized applying the delegated review fixes and proceeding to
  evaluation without another Opus run. Freeze provenance therefore records
  user-authorized remediation, not a second Opus review.

### Stale test cleanup

- Nineteen corrected tests passed; one failed because an earlier atomic patch
  removed the `re` import but not its now-meaningless normalization block.
- Removed that dead test code. The substantive shortcut-language assertions
  remain.

## 2026-08-11: Corrected benchmark frozen

- Applied every reproducible Opus finding without rerunning the paid review,
  as directed by the user.
- Froze the corrected 60-case artifact with user-authorized remediation
  provenance; this makes the benchmark evaluation-ready but does not accept
  the separate Phase 6 model-quality gate.
- Focused benchmark tests: 20 passed.
- Complete Phase 6 test selection: 71 passed.
- Full backend regression suite: 227 passed.
- Repository-wide Ruff and diff checks: clean, apart from known warnings for
  inaccessible pre-existing `.tmp/pytest-*` directories.
- Deterministic regeneration produced the same benchmark file digest.
- The final technical audit passes and reports `evaluation_ready: true`.
