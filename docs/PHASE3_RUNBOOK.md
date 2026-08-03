# Phase 3 Onboarding Runbook

This walkthrough verifies product/ICP onboarding and the human claim-review
boundary in the browser. Research and evidence are deterministic fixtures
derived from submitted inputs; they are not live public-source research.

## 1. Start the backend

From the repository root:

```powershell
uv run uvicorn src.runtime.api:app --reload --host 127.0.0.1 --port 8001
```

Port 8001 avoids the local port 8000 conflict encountered during Phase 2.
Campaign state is process-local and is cleared when this command stops.

## 2. Start the frontend

Open a second PowerShell terminal in the repository root:

```powershell
Set-Location frontend
$env:GTM_API_PROXY_TARGET = "http://127.0.0.1:8001"
npm.cmd run dev
```

Open the local URL printed by Vite. The browser sends relative `/campaigns`
requests through Vite's local proxy, so no CORS configuration is needed.

## 3. Verify the first product and ICP

Submit this logistics example:

- Product: `RouteSignal`
- URL: `https://example.com/routesignal`
- Description: `Highlights recurring delivery exceptions.`
- Capability: `exception reporting`
- Limitation: `requires dispatch data`
- Industry: `logistics`
- Company size: `mid-market`
- Target role: `Head of Operations`
- Pain: `manual exception review`

Confirm that:

- the proposed profile repeats the submitted product and ICP accurately;
- the page clearly labels the evidence as a deterministic fixture;
- every claim displays its evidence and uncertainty;
- authorization remains disabled while a claim is pending;
- rejecting every claim keeps authorization disabled;
- editing a claim requires changed wording and evidence attestation;
- reopening an approved claim's editor returns that claim to pending.

Approve at least one claim and explicitly reject the rest. For one approved
claim, use the edit flow and attest that its evidence supports the wording.
Authorize the completed review.

Expected result: the page displays `Claims locked. Prospecting is next.`, the
API state is `awaiting_prospect_selection`, the original proposal remains
unchanged, and the ledger distinguishes proposed wording from user-edited,
attested wording.

## 4. Verify a contrasting product and ICP

Select **Start another campaign**, then submit this security example:

- Product: `GuardLedger`
- URL: `https://example.com/guardledger`
- Description: `Summarizes access review activity for security teams.`
- Capability: `access review summaries`
- Limitation: `requires identity-provider exports`
- Industry: `cybersecurity`
- Company size: `enterprise`
- Target role: `Security Operations Lead`
- Pain: `manual access review`

Confirm the profile, evidence, and proposed claims contain the second inputs
and no values from the first campaign. Complete all claim decisions and verify
the same completion state.

## 5. Record the manual gate

Phase 3 is manually approved when both contrasting configurations complete,
all pending/all-rejected barriers behave as documented, edited wording
requires attestation, and no stale first-campaign values appear in the second
campaign. Record the result in `docs/PHASE_LOG.md` before the phase push.
