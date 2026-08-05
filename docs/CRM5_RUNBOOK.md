# CRM-5 Manual Verification

CRM-5 demonstrates an explainable revenue ledger. Amounts are integer minor
units, so `10000` means `$100.00` when the currency is USD.

## Create a fixture company, pipeline, and deal

```powershell
$headers = @{ "X-Tenant-ID" = "tenant-0001" }

Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8001/crm/companies" `
  -Headers $headers -ContentType "application/json" `
  -Body (@{ company_id = "company-revenue0001"; name = "Revenue Fixture Co" } | ConvertTo-Json)

Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8001/crm/pipelines" `
  -Headers $headers -ContentType "application/json" `
  -Body (@{
    pipeline_id = "pipeline-revenue0001"
    name = "Revenue fixture"
    stages = @(@{
      stage_id = "stage-revenue0001"
      name = "Qualified"
      position = 1
      probability = 0.5
    })
  } | ConvertTo-Json -Depth 6)

Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8001/crm/deals" `
  -Headers $headers -ContentType "application/json" `
  -Body (@{
    deal_id = "deal-revenue0001"
    company_id = "company-revenue0001"
    pipeline_id = "pipeline-revenue0001"
    stage_id = "stage-revenue0001"
    name = "Revenue fixture deal"
    amount_minor = 20000
    currency = "USD"
    idempotency_key = "deal-revenue0001"
  } | ConvertTo-Json)
```

## Ingest effective-time events

Submit conversion at `$100.00`, expansion to `$150.00`, and cancellation to
zero. The same idempotency key may be replayed safely.

```powershell
$events = @(
  @{
    subscription_id = "subscription-revenue0001"
    company_id = "company-revenue0001"
    event_type = "converted"
    effective_at = "2026-08-01T12:00:00Z"
    recorded_at = "2026-08-05T12:00:00Z"
    mrr_minor_after = 10000
    currency = "USD"
    idempotency_key = "revenue-conversion0001"
  },
  @{
    subscription_id = "subscription-revenue0001"
    company_id = "company-revenue0001"
    event_type = "expanded"
    effective_at = "2026-08-03T12:00:00Z"
    recorded_at = "2026-08-05T12:00:00Z"
    mrr_minor_after = 15000
    currency = "USD"
    idempotency_key = "revenue-expansion0001"
  },
  @{
    subscription_id = "subscription-revenue0001"
    company_id = "company-revenue0001"
    event_type = "cancelled"
    effective_at = "2026-08-04T12:00:00Z"
    recorded_at = "2026-08-06T12:00:00Z"
    mrr_minor_after = 0
    currency = "USD"
    idempotency_key = "revenue-cancel0001"
  }
)
foreach ($event in $events) {
  Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8001/crm/revenue/events" `
    -Headers $headers -ContentType "application/json" `
    -Body ($event | ConvertTo-Json)
}
```

## Review the report

```powershell
$report = Invoke-RestMethod `
  -Uri "http://127.0.0.1:8001/crm/revenue/report?as_of=2026-08-05&currency=USD" `
  -Headers $headers
$report | Select-Object mrr_minor, new_business, expansion, contraction, churn, pipeline_value, forecast_value, warnings
```

Confirm MRR is `0`, new business is `10000`, expansion is `5000`, churn is
`15000`, pipeline value is `20000`, and forecast value is `10000`. Confirm the
late cancellation appears as a `late_arrival` warning and metric event IDs
explain each total.

Finally, call `POST /agent/runs` with goal `Show the revenue report` and confirm
the read-only `crm.revenue_report` tool completes without an approval gate.
