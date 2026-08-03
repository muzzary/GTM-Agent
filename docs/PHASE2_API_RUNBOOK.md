# Phase 2 API Runbook

This walkthrough exercises the deterministic backend walking skeleton. It
does not call public sources or a live model, and all campaign state is lost
when the backend process stops.

## 1. Start the backend

From the repository root:

```powershell
uv run uvicorn src.runtime.api:app --reload
```

If another local application already uses port 8000, choose an available port:

```powershell
uv run uvicorn src.runtime.api:app --reload --host 127.0.0.1 --port 8001
```

Open a second PowerShell terminal in the repository root for the remaining
steps. Set the base URL to the port printed by Uvicorn:

```powershell
$baseUrl = "http://127.0.0.1:8000"
Invoke-RestMethod "$baseUrl/health"
```

Use `http://127.0.0.1:8001` instead when Uvicorn was started on port 8001.

## 2. Create a campaign

```powershell
$campaignBody = @{
    product_name = "RouteSignal"
    product_url = "https://example.com/routesignal"
    short_description = "Highlights recurring delivery exceptions."
    known_capabilities = @("exception reporting")
    known_limitations = @("requires dispatch data")
    icp = @{
        industries = @("logistics")
        company_size = "mid-market"
        roles = @("Head of Operations")
        pain_hypotheses = @("manual exception review")
    }
} | ConvertTo-Json -Depth 4

$campaign = Invoke-RestMethod `
    -Method Post `
    -Uri "$baseUrl/campaigns" `
    -ContentType "application/json" `
    -Body $campaignBody

$campaign.state
$campaign.claims
```

The state should be `awaiting_claim_approval` and two fixture claims should be
visible.

## 3. Decide every claim

This example approves the first claim and rejects the second.

```powershell
$decisions = for ($index = 0; $index -lt $campaign.claims.Count; $index++) {
    @{
        claim_id = $campaign.claims[$index].claim_id
        decision = if ($index -eq 0) { "approved" } else { "rejected" }
    }
}

$decisionBody = @{ decisions = @($decisions) } | ConvertTo-Json -Depth 4
$campaign = Invoke-RestMethod `
    -Method Post `
    -Uri "$baseUrl/campaigns/$($campaign.campaign_id)/claim-decisions" `
    -ContentType "application/json" `
    -Body $decisionBody

$campaign.state
```

The state should be `awaiting_prospect_selection`. Submitting an incomplete
decision set or rejecting every claim returns HTTP 409 without changing the
campaign.

## 4. Select a fixture prospect

```powershell
$prospects = Invoke-RestMethod `
    -Uri "$baseUrl/campaigns/$($campaign.campaign_id)/prospects"

$selected = $prospects[0]
$campaign = Invoke-RestMethod `
    -Method Post `
    -Uri "$baseUrl/campaigns/$($campaign.campaign_id)/prospects/$($selected.prospect_id)/select"

$campaign.state
```

The state should be `awaiting_prospect_research`.

## 5. Complete the synthetic prospect-research gate

```powershell
$researchRequest = @{
    request_id = "research-request-fixture1"
} | ConvertTo-Json

$research = Invoke-RestMethod `
    -Method Post `
    -Uri "$baseUrl/campaigns/$($campaign.campaign_id)/prospects/$($selected.prospect_id)/research-runs" `
    -ContentType "application/json" `
    -Body $researchRequest

$campaign = $research.campaign
$campaign.state
```

The state should be `prospect_researched`. This remains synthetic fixture
research; the Phase 4 runbook covers live public research.

## 6. Generate and inspect the validated draft

```powershell
$campaign = Invoke-RestMethod `
    -Method Post `
    -Uri "$baseUrl/campaigns/$($campaign.campaign_id)/draft"

$campaign.state
$campaign.draft
$campaign.evaluation
```

The state should be `draft_ready`, and every evaluation check should pass.
The draft is fixture output only and must not be represented as live research
or model inference.

## 7. Inspect the ordered trace

```powershell
$trace = Invoke-RestMethod `
    -Uri "$baseUrl/campaigns/$($campaign.campaign_id)/trace"

$trace | Select-Object sequence, event_type, summary
```

The trace should contain eleven ordered events, from `campaign_created` through
`draft_evaluated`.
