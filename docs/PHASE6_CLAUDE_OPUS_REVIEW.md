# Phase 6 Claude Opus 4.8 Review

## Review metadata

- Date: 2026-08-10
- Reviewer: Claude Code 2.1.211 using `claude-opus-4-8`
- Effort: maximum
- Access: read-only; no files edited by Claude
- Cases individually reviewed: 60 of 60
- API cost: USD 2.435928
- Verdict: `APPROVE_WITH_FIXES`

Claude read the complete benchmark manifest, Phase 6 specification, manual
review guide, benchmark schema, and benchmark auditor. It explicitly confirmed
individual review of cases `case-phase6-001` through `case-phase6-060`.

## Counts

- Cases passing without a case-specific fix: 55
- Cases needing a case-specific fix: 5
- P0 findings: 0
- P1 findings: 0
- P2 findings: 8, including the five case findings
- P3 findings: 4

Claude independently confirmed the exact 30/15/8/7 status distribution, 15
protected adversarial cases, all required coverage counts, controlled synthetic
provenance, unique company/prospect identities, pending-review lifecycle, and
absence of gold email prose.

## Case-specific fixes

The five weak-evidence cases are ambiguous because the evidence only says the
company operates across several locations, while the hypothesis presupposes an
observed domain workflow and the expected status is `drafted`.

| Case | Product category | Required correction |
| --- | --- | --- |
| `case-phase6-002` | Reporting automation | Use a weak but reporting-relevant signal and remove the unsupported “observed reporting process” presupposition. |
| `case-phase6-014` | Security asset inventory | Use a weak cloud-asset-relevant signal and remove the unsupported “observed cloud assets process” presupposition. |
| `case-phase6-026` | Developer productivity | Use a weak CI-relevant signal and remove the unsupported “observed CI failures process” presupposition. |
| `case-phase6-038` | Support knowledge workflow | Use a weak support-knowledge-relevant signal and remove the unsupported “observed support knowledge process” presupposition. |
| `case-phase6-050` | CRM data hygiene | Use a weak CRM-data-relevant signal and remove the unsupported “observed CRM records process” presupposition. |

Recommended evidence is a thin but domain-relevant public signal, such as a
role description mentioning the relevant workflow. That preserves the `weak`
condition while making `drafted` a clear, fair expected behavior.

## Systemic findings

### P2: Template shortcuts

Evidence and hypotheses have very little surface variation. A model could learn
status from phrases such as “2023 archive,” “several locations,” or “requests no
further sales outreach” without demonstrating grounding. Vary evidence syntax,
source shapes, and product-specific hypotheses before freezing.

### P2: Arbitrary required claim

Each drafted case selects one rotating required claim even when another
approved claim would be equally valid. If exact-match scoring is used, this
would create false negatives. Before evaluation, either define the expectation
as at least one acceptable approved claim or make each case's evidence and
scenario specifically motivate the selected claim.

### P2: Flattened pain hypotheses

Every product reduces its possible pain to “coordination work.” Security asset
inventory, CI productivity, support knowledge, reporting, and CRM hygiene need
distinct, uncertain hypotheses that reflect their real domains.

### P3: Uniform operations roles

All five product categories use the same Operations Specialist-to-COO role
ladder. Security, developer tooling, and support products should use their
natural buying centers, such as security, engineering, and customer-support
leadership.

### P3: Protected-set composition

All 15 protected adversarial cases are drafted cases with benign-looking input;
the hidden tags describe output failure modes. The protected subset currently
contains no safe-abstention cases or input-side bait. Add both in a later
revision while retaining exact protected counts.

### P3: Missing invasive-personalization case

`invasive_personalization` exists in the tag contract but appears in no case.
Add a controlled evidence input containing detail that must not be echoed in
outreach.

### P3: Artificial abstention wording

Disqualification and opt-out signals are semantically sufficient and correctly
labeled, but their wording is highly explicit and repetitive. Natural variants
would improve realism and reduce shortcut learning.

## Independent verification

Codex independently inspected the five cited weak cases, the complete role
distribution, adversarial-tag counts, and protected-case IDs. The material
findings above reproduce against the committed manifest.

## Disposition

Do not freeze this candidate yet. Apply the five case corrections and tighten
the systemic benchmark design, regenerate hashes, rerun audits/tests, and then
request a final semantic re-review. This does not change the successful Phase 6
technical pilot or accept the Phase 6 model-quality gate.
