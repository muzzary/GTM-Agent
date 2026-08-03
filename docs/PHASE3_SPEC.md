# Phase 3 Specification: Product Onboarding and Claim Review

**Status:** Approved

## Objective

Build the first interactive React workflow on top of the Phase 2 API. A user
can submit a product and ICP, inspect the deterministic proposed profile and
its evidence, review every claim, and authorize only valid reviewed wording
for later stages.

Phase 3 succeeds when two contrasting product/ICP configurations can complete
onboarding and reach `awaiting_prospect_selection`, while incomplete, rejected,
stale, malformed, or cross-campaign decisions cannot authorize claim use.

## Assumptions for approval

1. A claim edit is a human wording correction, not new researched evidence.
2. An edited claim requires explicit approval plus an evidence-attestation
   checkbox confirming that the displayed evidence still supports the wording.
3. The proposed claim remains immutable. Its approval record stores the exact
   reviewed wording authorized downstream.
4. The approval history remains process-local in Phase 3. It is review history
   for the MVP, not a durable regulatory audit log.
5. Authentication and multi-user authorization remain out of scope. Here,
   "authorization boundary" means that only an explicit valid claim approval
   can authorize downstream use.
6. The browser reaches FastAPI through the Vite development proxy. Phase 3
   does not change CORS policy.

## Reconciled architecture decisions

### Immutable proposed claims and versioned approval wording

- `ProductClaim.text` remains the wording originally proposed from fixture
  evidence; review never overwrites it.
- `ClaimDecision` gains optional `edited_text` and `evidence_attested` fields.
- An edit is accepted only with `decision=approved`, meaningful normalized
  text, changed wording, and `evidence_attested=true`.
- `ApprovalRecord` becomes the exact authorized version and records:
  `claim_id`, decision, original wording, reviewed wording, evidence IDs,
  wording source (`proposed` or `user_edited`), and evidence attestation.
- Rejected records always retain the original wording and cannot carry an edit.
- Positioning and outreach records reference both claim IDs and approval IDs.
- Deterministic generation consumes approved `ApprovalRecord.reviewed_text`,
  never pending/rejected `ProductClaim.text`.
- The Phase 3 fixture test requires the exact reviewed wording and approval ID
  to appear in the downstream draft provenance. Semantic support checks for
  real model paraphrases remain a Phase 5 concern.

### Contractual campaign invariants

- Campaign validation ties every approval to a campaign claim and requires its
  original wording and evidence IDs to match the immutable proposal.
- Approved edits require user attestation; rejected records cannot change
  wording.
- Claim status must match its approval decision.
- Draft and positioning approval IDs must resolve to approved records.
- The repository validates a complete campaign before saving it.

### Input normalization and bounds

Backend validation is authoritative and rejects whitespace-only values before
fixture processing. Frontend validation mirrors these documented limits:

| Input | Limit |
| --- | --- |
| Product name | 1-120 normalized characters |
| Product URL | Optional HTTP(S) URL |
| Description | 1-1,000 normalized characters |
| Capability or limitation | 1-200 characters each; at most 24 |
| Industry, company size, or role | 1-120 characters each |
| Pain hypothesis | 1-500 characters each; at most 12 |
| Edited claim | 1-500 normalized characters |

Multi-value frontend fields use one value per line, trim surrounding
whitespace, remove blank lines, preserve order, and reject duplicates. Control
characters other than normal textarea line breaks are rejected at the API
boundary.

### Decision integrity, retries, and concurrency

- The server rejects missing, duplicate, extra, unknown, and cross-campaign
  claim IDs.
- The workflow serializes state-changing commands with a process-local lock,
  matching the single-process in-memory MVP boundary.
- Repeating an identical completed decision batch is idempotent and returns the
  current campaign without another audit record or prospect-ranking run.
- A different replay after decisions are locked returns HTTP 409.
- The UI disables duplicate in-flight submissions and editing any claim resets
  its staged decision to pending.
- Multi-process concurrency and durable idempotency are deferred with database
  persistence after the MVP.

### Frontend/API boundary

- `frontend/src/api/campaign.ts` owns request/response types, fetch handling,
  error normalization, and runtime guards.
- Runtime guards validate every field the UI trusts: campaign ownership,
  supported state, unique claim/evidence/approval IDs, resolvable evidence,
  and bounded strings.
- Requests use relative `/campaigns` paths. Vite proxies them to
  `GTM_API_PROXY_TARGET`, defaulting to `http://127.0.0.1:8000`; port 8001 can
  be selected without a code or CORS change.
- React renders all text normally and never uses raw HTML. Product URLs are
  displayed as text in Phase 3, not fetched or opened by the server.

## User workflow

### Step 1: Product and ICP configuration

The form collects product name, optional URL, description, capabilities,
limitations, industries, company size, target roles, and pain hypotheses.
Every control has a visible label, help text, limits, and associated error
message. Submission shows an announced loading state and an actionable error
without losing entered values.

### Step 2: Proposed profile and claim review

The UI displays the normalized product/ICP profile, every fixture evidence
record, uncertainty, and an explicit "deterministic fixture—not live research"
notice. Each claim is grouped with its evidence and offers native keyboard
buttons for Approve, Reject, and Edit.

Opening or changing an editor resets that claim to pending. Saving edited
wording requires the evidence-attestation checkbox, followed by a separate
Approve action. Rejection discards staged edits.

The review cannot be submitted while any claim is pending, no claim is
approved, an approved edit lacks attestation, or a request is in flight. A
visible status summary explains each unmet condition instead of relying only
on a disabled button.

### Step 3: Onboarding completion

A successful review displays the API state `awaiting_prospect_selection`, the
locked decision audit, and a clear Phase 4 handoff message. "Start another
campaign" resets local state only when no request is active.

## Accessibility requirements

- Preserve heading order and use `fieldset`/`legend` for ICP and claim groups.
- Associate every validation message with its control using `aria-describedby`.
- Announce loading, API errors, validation summaries, and step completion with
  appropriate live regions.
- Use `aria-pressed` on Approve/Reject controls and text labels in addition to
  color.
- Focus the validation summary after a failed submission, the profile heading
  after campaign creation, and the completion heading after claim review.
- Test accessible names, pending-state explanation, edit invalidation, and
  focus transitions with Testing Library.

## Technology and dependencies

- Existing React 19, TypeScript, Vite, Vitest, and Testing Library stack.
- Existing Python 3.12, FastAPI, Pydantic, and Pytest stack.
- Standard-library locking and normalization utilities.
- No new Python or npm dependency.

## Commands

```powershell
uv run pytest -q
uv run ruff check .
uv lock --check
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run build
```

Manual development with the occupied-port workaround:

```powershell
uv run uvicorn src.runtime.api:app --reload --host 127.0.0.1 --port 8001
$env:GTM_API_PROXY_TARGET = "http://127.0.0.1:8001"
npm.cmd --prefix frontend run dev
```

## Testing strategy

### Backend contracts and workflow

- Reject blank/oversized list values and edits with controlled 422 responses.
- Reject rejected edits, unattested edits, duplicate/extra/cross-campaign IDs,
  and non-identical replays.
- Verify identical retry idempotency and one audit record per claim.
- Verify proposed text remains unchanged and approved review text is used by
  positioning/draft output with matching approval IDs.
- Verify campaign invariants reject malformed audit/provenance combinations.
- Keep all Phase 0-2 tests green.

### Frontend units and components

- Test newline parsing, normalization, limits, duplicates, and payload shape.
- Test malformed API responses, duplicate IDs, ownership mismatches, and
  unresolved evidence.
- Test required-field and server errors without losing input.
- Test profile/evidence provenance display and fixture labeling.
- Test pending and zero-approved barriers, approve-then-edit invalidation,
  repeated edits, attestation, rejection, duplicate-click prevention, and
  exact decision payloads.
- Test accessible names, live announcements, focus movement, and reset for a
  second contrasting campaign.

## Implementation tasks

### Task 1: Harden input and review contracts

**Files:** `src/schemas/campaign.py`, `tests/test_campaign_schemas.py`,
`tests/test_campaign_api.py`

**Acceptance:** Per-item bounds and normalization reject malformed input;
approval records enforce immutable proposal and reviewed-wording semantics.

**Verify:** Targeted schema/API tests fail first, then pass; Ruff is clean.

### Task 2: Enforce approved wording and retry safety

**Files:** `src/runtime/workflow.py`, `src/runtime/fixtures.py`,
`tests/test_campaign_workflow.py`, `tests/test_campaign_api.py`

**Acceptance:** Approved review records are the sole downstream text source;
identical retries are idempotent; conflicting/cross-campaign decisions fail
without mutation.

**Verify:** Workflow/API tests cover exact text, approval provenance,
concurrency boundary, and unchanged state after rejection.

### Task 3: Add the typed frontend API boundary

**Files:** `frontend/src/api/campaign.ts`,
`frontend/src/api/campaign.test.ts`, `frontend/vite.config.ts`

**Acceptance:** Typed requests, defensive response guards, normalized errors,
and configurable same-origin proxy work without CORS or new packages.

**Verify:** API-client tests, TypeScript, frontend lint, and build pass.

### Task 4: Build and validate the onboarding form

**Files:** `frontend/src/components/CampaignForm.tsx`,
`frontend/src/components/CampaignForm.test.tsx`,
`frontend/src/forms/campaign-input.ts`

**Acceptance:** Accessible inputs produce backend-compatible payloads and show
field-linked validation without losing user input.

**Verify:** Form unit/component tests pass at required and boundary values.

### Task 5: Build claim review and app orchestration

**Files:** `frontend/src/components/ClaimReview.tsx`,
`frontend/src/components/ClaimReview.test.tsx`, `frontend/src/App.tsx`,
`frontend/src/App.test.tsx`, `frontend/src/index.css`

**Acceptance:** The UI displays fixture provenance, requires valid decisions
and edit attestation, prevents stale/duplicate submissions, reaches the API
handoff state, and resets for another campaign.

**Verify:** Component flow tests pass; browser manual checks cover keyboard,
focus, 320/768/1024/1440px layouts, loading, errors, and two campaigns.

### Task 6: Final documentation and phase verification

**Files:** `README.md`, `DIRECTORY_MAP.md`, `docs/PHASE_LOG.md`,
`docs/PHASE3_RUNBOOK.md`

**Acceptance:** Setup, proxy-port behavior, limitations, manual workflow, and
phase verification are current and reproducible.

**Verify:** Full backend/frontend gates, dependency audit, secret scan,
self-review, manual gate, atomic commits, and branch push.

## Boundaries

### Always

- Validate in both frontend and backend; backend remains authoritative.
- Preserve immutable proposed wording and exact authorized reviewed wording.
- Treat fixture evidence and API responses as untrusted display data.
- Keep user-visible provenance and uncertainty explicit.

### Ask first

- Any dependency, CORS, authentication, persistence, or API-hosting change.
- Any relaxation of evidence attestation or claim-approval gates.

### Never

- Present fixture evidence as live research.
- Authorize an edited, pending, rejected, malformed, or unattested claim.
- Fetch the submitted product URL or render user content as raw HTML.
- Claim the in-memory review history is a durable compliance audit.

## Manual acceptance

1. Complete onboarding for a logistics operations product/ICP.
2. Complete onboarding for a contrasting security or finance product/ICP.
3. In each campaign, inspect fixture evidence, edit and attest one claim,
   reject another where possible, and reach `awaiting_prospect_selection`.
4. Confirm errors, disabled-state explanations, keyboard controls, focus, and
   responsive layouts are understandable.

## Open questions

None after plan approval. Persistence, real evidence revalidation, and
multi-user authorization remain explicit post-Phase-3 work.
