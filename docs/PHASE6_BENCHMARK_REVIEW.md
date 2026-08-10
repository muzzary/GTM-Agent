# Phase 6 Benchmark Review

## Current state

`configs/phase6/benchmark-v2.json` is a technically validated, controlled
synthetic benchmark. Its lifecycle is `frozen` and the audit reports
`evaluation_ready: true` after user-authorized remediation of the Opus review.

The benchmark deliberately contains no target email prose. It measures whether
a model can produce grounded outreach or safely abstain from structured facts,
rather than matching a reference email.

## Coverage

| Dimension | Distribution |
| --- | --- |
| Cases | 60 |
| Product categories | 5 categories, 12 cases each |
| ICP patterns | 5 patterns, 12 cases each |
| Role tiers | 5 tiers, 12 cases each |
| Drafted | 30 |
| Needs more evidence | 15 |
| Disqualified | 8 |
| Opted out | 7 |
| Evidence conditions | 40 strong; 5 each weak, conflicting, stale, absent |
| Outreach scenarios | 35 initial; 25 follow-up |
| Protected adversarial subset | 15 |

The five product categories are reporting automation, security asset inventory,
developer productivity, support knowledge workflow, and CRM data hygiene.

## Manual semantic checklist

Review the JSON by product in twelve-case blocks. For every case confirm:

1. the product claim is specific, plausible, and no stronger than its controlled
   synthetic source;
2. each evidence excerpt supports only what its evidence condition says;
3. the expected status is correct, especially for weak, conflicting, stale,
   absent, disqualified, and opted-out inputs;
4. acceptable claim IDs contain every valid approved option, required evidence
   IDs identify the personalization anchor, and both are empty for abstentions;
5. adversarial tags describe a real trap without revealing it through the typed
   prompt-input projection;
6. the target role, ICP, and scenario are coherent enough for meaningful
   outreach evaluation;
7. the case is not copied from the pilot, Phase 1 benchmark, or future training
   examples.

All 60 cases now carry reviewed provenance, the manifest lifecycle is `frozen`,
and every case and manifest hash was regenerated. Any content change requires a
new version, review decision, and complete hash regeneration.

## Interpretation boundary

Passing this benchmark supports claims about contract adherence, grounding,
safe abstention, personalization discipline, and CTA integrity under controlled
conditions. It does not prove that an email will earn replies or conversions;
that requires separately consented real-world outcome evaluation.
