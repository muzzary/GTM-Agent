# CRM and Revenue MVP Plan

## Purpose

Extend the existing GTM-Agent into a small agent-first CRM and revenue
workflow. The MVP will connect prospect research to companies, contacts, deals,
pipeline stages, activities, and basic revenue reporting. The fine-tuned model
will propose plans and tool calls; deterministic backend services will validate
and execute those calls.

This is a portfolio-grade CRM vertical slice, not a production replacement for
Salesforce, HubSpot, billing infrastructure, or graph8's full platform.

## MVP outcome

A user can:

1. Discover and research a prospect through the existing GTM workflow.
2. Create or match the prospect as a CRM company.
3. Add a contact and create a deal in a selected pipeline.
4. Ask the agent to update CRM records through approved tools.
5. Move the deal through valid stages with idempotent operations.
6. Record activities and research evidence on the deal timeline.
7. View pipeline value and basic MRR, new-business, and churn metrics.

## Architecture decisions

- Keep the existing GTM campaign workflow and add CRM as a connected bounded
  context; do not rewrite the research system.
- Use one service layer for both HTTP endpoints and agent tools. The UI and
  model must not have separate business logic paths.
- Use a local SQLite repository for the first vertical slice so the MVP stays
  reproducible and adds no dependency. Keep repository interfaces portable to
  PostgreSQL.
- Require `tenant_id` on every CRM record and query even before authentication
  is implemented. This prevents a later multi-tenant migration from changing
  every contract.
- Treat the model as an untrusted planner. It may suggest a tool call, but the
  runtime validates schema, ownership, permissions, state transitions, and
  approval requirements before execution.
- Start with a test-double agent loop and validated structured model outputs.
  Real Colab inference can be connected after the tool contract is stable.
- Keep quote-to-cash, full provider sync, Kubernetes, and production billing
  outside the first MVP vertical slice.

## Dependency graph

```text
CRM contracts and invariants
        ↓
SQLite schema and repositories
        ↓
CRM service layer
        ├── REST API
        ├── React CRM workspace
        └── Agent tool registry and execution loop
                ↓
        GTM-to-CRM linking and activities
                ↓
        Revenue event ledger and reports
                ↓
        PostgreSQL/provider integrations (post-MVP)
```

## Phase CRM-1: CRM domain and persistence

**Status:** Accepted after manual verification.

**Goal:** Establish the data model and repository boundaries without changing
the existing GTM behavior.

**Build:**

- Companies, contacts, pipelines, pipeline stages, deals, custom fields, and
  activities.
- Tenant ownership and stable external IDs.
- Valid stage-transition rules and record ownership checks.
- SQLite schema, indexes, repository interfaces, and seed fixtures.

**Acceptance:**

- A company, contact, and deal can be created and retrieved for one tenant.
- Cross-tenant reads and writes are rejected.
- Invalid stage transitions and duplicate idempotency keys are rejected.
- Existing GTM tests remain green.

**Verification:** Backend unit, repository, isolation, constraint, and
transition tests; migration/restart test; Ruff and lock checks.

**No new dependency expected.**

## Phase CRM-2: CRM API and UI vertical slice

**Goal:** Make the CRM useful to a human before adding model-driven actions.

**Build:**

- Endpoints for company, contact, pipeline, deal, activity, and custom-field
  operations.
- Pipeline board and deal detail view.
- Prospect-to-company conversion from the existing research workspace.
- Campaign-aware navigation between prospects, research, and CRM records.

**Acceptance:**

- A researched prospect can become a CRM company without losing evidence links.
- A user can create a contact and deal, move the deal through valid stages, and
  see the activity timeline.
- The UI displays concise research points with expandable evidence details.

**Verification:** API contract tests, frontend component tests, browser
walkthrough, typecheck, lint, and production build.

**Depends on:** CRM-1.

## Phase CRM-3: Agent tools and controlled execution loop

**Goal:** Make the CRM genuinely agentic rather than only a fixed pipeline.

**Build:**

- Versioned tool definitions for CRM and GTM operations.
- Tool argument validation and result schemas.
- Agent loop that can inspect state, choose a tool, observe the result, and
  continue or request approval.
- Permission checks, idempotency keys, bounded retries, explicit failures, and
  complete tool-call traces.
- Test-double model path first; Colab model integration behind the existing
  validated inference boundary.

**Acceptance:**

- Given a user goal, the agent can research a prospect, create or match a CRM
  company, create a deal, and stop for approval before a sensitive action.
- The model cannot directly mutate storage or bypass tool validation.
- Replaying the same tool call does not create duplicate records.
- Tool failures and approval pauses are visible in the trace.

**Verification:** Tool-contract tests, adversarial model-output tests,
idempotency tests, approval tests, trace tests, and an end-to-end agent fixture.

**Depends on:** CRM-1 and CRM-2 contracts.

## Phase CRM-4: GTM-to-CRM workflow integration

**Goal:** Join the existing prospecting system to the CRM lifecycle.

**Build:**

- Prospect-to-company matching using normalized domains and reviewed evidence.
- Contact creation only from user-provided or permitted public business data.
- Deal creation from an approved positioning/outreach workflow.
- Evidence, claims, positioning, outreach drafts, and user decisions as CRM
  activities or linked artifacts.
- Duplicate matching and conflict review.

**Acceptance:**

- A completed prospect research run can create a defensible CRM record.
- Unapproved product claims cannot appear in CRM activities or outreach.
- Duplicate companies are surfaced for review instead of silently merged.
- Research and CRM traces can be followed from campaign to deal.

**Verification:** Full workflow tests, duplicate/conflict fixtures, privacy
tests, manual campaign walkthrough, and regression suite.

**Depends on:** CRM-2 and CRM-3.

## Phase CRM-5: Revenue event ledger and reporting

**Goal:** Demonstrate the revenue-engineering side of the role with explainable
metrics.

**Build:**

- Revenue events for trial start, conversion, expansion, contraction,
  cancellation, and reactivation.
- Subscription snapshots and effective-time handling.
- MRR, new business, expansion, churn, pipeline value, and simple forecast
  reports.
- Reconciliation warnings when event data is incomplete or inconsistent.

**Acceptance:**

- A fixture dataset produces reproducible MRR and churn totals.
- Reports explain which events contributed to each metric.
- Duplicate or late events do not double-count revenue.
- Incomplete billing data is marked uncertain rather than silently treated as
  truth.

**Verification:** Event-ordering, duplicate, late-arrival, reconciliation,
metric, and API tests; manual report review.

**Depends on:** CRM-1 and CRM-4.

## Post-MVP extensions

These should follow the vertical slice rather than block it:

- PostgreSQL adapter, transaction tuning, indexes, and load tests.
- One CRM synchronization adapter, preferably HubSpot first.
- Webhook ingestion, rate limits, cursor sync, conflict resolution, and an
  outbox/dead-letter model.
- Quote builder and Stripe test-mode billing adapter.
- E-signature provider boundary and signature-event handling.
- Redis/Temporal/Kubernetes deployment patterns.
- Salesforce and Pipedrive adapters after the first provider is proven.

PostgreSQL or provider SDK dependencies require a separate dependency review
before installation, as required by the repository rules.

## Main risks and controls

| Risk | Control |
| --- | --- |
| Model makes unsafe CRM mutations | Allowlisted tools, schemas, permissions, approvals, and traces |
| Duplicate companies or deals | Idempotency keys, normalized matching, and human conflict review |
| Tenant data leakage | Tenant-scoped repositories, ownership checks, and cross-tenant tests |
| Revenue metrics become misleading | Event ledger, effective timestamps, reconciliation, and uncertainty fields |
| Scope grows into a full CRM rebuild | Keep one complete vertical slice and defer provider/billing infrastructure |
| Colab endpoint is unavailable | Test-double path and validated result bundles keep the MVP demonstrable |

## Phase gate rules

Each CRM phase must finish with:

- Automated backend/frontend tests.
- Self-review for correctness, security, and unnecessary complexity.
- Updated phase log and README.
- Manual browser/API verification by the user.
- A commit and push before the next phase begins.
