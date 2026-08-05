# CRM-4 Manual Verification

CRM-4 links a completed selected-prospect research run to a CRM company. Use
the campaign ID from the current backend process; campaign state is local and
resets when Uvicorn restarts.

## Direct reviewed link

```powershell
$campaignId = "campaign-..."
$headers = @{ "X-Tenant-ID" = "tenant-0001" }

Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8001/campaigns/$campaignId/crm/company" `
  -Headers $headers `
  -ContentType "application/json" `
  -Body (@{ idempotency_key = "manual-link-0001" } | ConvertTo-Json)
```

Confirm the response has `status: linked`, a company with the campaign and
prospect source IDs, and a research activity. Repeat the same request and
confirm the existing company is returned with only one research activity.

## Agent approval gate

First request the action without approval:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8001/agent/runs" `
  -Headers $headers `
  -ContentType "application/json" `
  -Body (@{
    goal = "Link the selected prospect to CRM"
    campaign_id = $campaignId
  } | ConvertTo-Json)
```

Confirm the result is `approval_required` and no company was created. Repeat
with `approved_call_ids = @("tool-call-link-prospect-0001")` and confirm the
trace contains `tool_called`, `succeeded`, and `final`.

## Duplicate review

For a live prospect with an official website, create a CRM company first using
the same normalized domain, then run the reviewed link. Confirm the response
is `conflict_review`, contains the existing company ID, and does not merge or
create a second company. Fixture prospects without an official URL cannot
exercise domain matching, but they still preserve their source evidence.
