# Phase 6 Dataset and Outreach Rubric Research

**Research date:** 2026-08-09

## Decision snapshot

- The Phase 6 technical pilot succeeded: the pinned Qwen model trained and
  loaded a LoRA adapter, produced reproducible artifacts, and completed the
  unchanged benchmark without structural or identifier regressions.
- The Phase 6 quality gate remains unaccepted. The adapter did not improve on
  the base model, and manual review found unsupported fact combinations,
  citations that were not used in the message, generic copy, and missing CTAs.
- Do not train on a large public corpus as-is. No reviewed public source found
  combines direct B2B cold-email relevance, verified outcomes, clean commercial
  reuse terms, and the evidence/claim provenance required by this project.
- Build a reviewed first-party core and use public datasets only as bounded,
  attributed auxiliary material after row-level filtering and normalization.

This document is a research and design proposal. Changing the production rubric
or approval gates still requires explicit approval before implementation.

## Compatibility boundary

The approved base is `Qwen/Qwen3-4B-Instruct-2507`. Qwen documents Instruct
models as using the predefined chat template and recommends established SFT/LoRA
training frameworks. Future training rows should therefore normalize to
`system`/`user`/`assistant` messages and be rendered with the pinned tokenizer's
chat template rather than teaching a second ad-hoc transcript format.

Sources:

- [Qwen3 model concepts and ChatML template](https://github.com/QwenLM/Qwen3/blob/main/docs/source/getting_started/concepts.md)
- [Qwen3 fine-tuning guidance](https://github.com/QwenLM/Qwen3#finetuning)
- [Qwen SFT message-oriented JSONL example](https://qwen.readthedocs.io/en/v1.5/training/SFT/example.html)

External data is only compatible when it can be transformed into the project's
strict reviewed-example schema without losing provenance, license, split,
support, or reviewer fields. Format compatibility alone is not approval.

## Dataset findings

| Source | Size/license reported by source | Direct fit | Decision |
| --- | --- | --- | --- |
| Project-owned reviewed synthetic examples | Six pilot rows; project-controlled | Exact outreach contract, claims, evidence, and split controls | **Primary source. Expand substantially with human review.** |
| [Glaive Function Calling v2](https://huggingface.co/datasets/glaiveai/glaive-function-calling-v2) | 112,960 rows; Apache-2.0 | Generic tool selection, clarification, refusal, and JSON arguments | **Candidate auxiliary source.** Sample only relevant patterns, convert to the Qwen chat/tool contract, and re-review every retained row. |
| [gwenshap/sales-transcripts](https://huggingface.co/datasets/gwenshap/sales-transcripts) | 1,940 simulated transcript chunks; Apache-2.0 | Discovery, objection handling, and clarification language; not cold email or CRM tool use | **Candidate auxiliary source.** Use a small rewritten subset; never inherit fictional policies or product claims. |
| [Tenacious-Bench v0.1](https://huggingface.co/datasets/eyobed7b/tenacious-bench-dataset) | 274 synthetic B2B outbound tasks; CC BY 4.0 | Honesty flags, signal grounding, tone, and ICP suppression | **Evaluation/rubric candidate first.** It is small, domain-specific, recently published, and designed primarily as benchmark/judge data rather than generation SFT. Keep its held-out material out of training. |
| [DeepMost SaaS sales conversations](https://huggingface.co/datasets/DeepMostInnovations/saas-sales-conversations) | 100,000 synthetic conversations; Apache-2.0 | Broad SaaS sales dialogue and synthetic outcome labels; not evidence-grounded cold email | **Hold for sampled audit.** Do not ingest its 7.17 GB file or automatic effectiveness labels without quality and duplication analysis. |
| [Narrative Function Calling v1](https://huggingface.co/datasets/narrative-io/narrative-function-calling-v1) | 147,047 normalized conversations; CC BY 4.0 per its card | Parseable tool calls and multi-turn tool responses | **Hold.** Verify the full attribution/license chain for incorporated Glaive and xLAM material before any use. It duplicates capabilities available from the simpler Glaive source. |
| [Salesforce CRMArena-Pro](https://huggingface.co/datasets/Salesforce/CRMArenaPro) | About 8,600 CRM benchmark tasks; CC BY-NC 4.0 | Strong B2B/B2C CRM task coverage, including lead qualification and stage correction | **Research/evaluation only; exclude from product training.** The non-commercial restriction is incompatible with a reusable product dataset. |
| [Salesforce APIGen-MT-5k](https://huggingface.co/datasets/Salesforce/APIGen-MT-5k) | 5,000 verified multi-turn tool trajectories; CC BY-NC 4.0 | High-quality multi-turn tool behavior, but retail/airline rather than CRM | **Exclude from product training** because of the non-commercial license. Use the paper's verification ideas, not its rows. |
| [monodox sales-and-marketing intelligence](https://huggingface.co/datasets/monodox/sales-and-marketing-intelligence) | One nested record; Apache-2.0 | One direct cold-email example | **Reject as a training source.** It is too small to add useful coverage. |
| [RAS1981 outreach-agent-sft-stages](https://huggingface.co/datasets/RAS1981/outreach-agent-sft-stages) | 9,201 Russian real-estate conversations; no license declared in the card | Wrong language/domain and unclear permission | **Reject.** |

### What the public-data search did not find

The search did not identify a public dataset of real B2B cold emails with all of
the following: recipient consent or safe de-identification, reliable send/reply
outcomes, message-level product/prospect evidence, and an explicit permissive
license. Synthetic conversion labels are not real business outcomes and must not
be used as proof that a writing pattern works.

## Evidence on outreach behavior

The strongest directly relevant public evidence found is proprietary,
observational Gong Labs analysis. It is useful for design hypotheses, but it is
not a randomized experiment and should not be treated as universal causation.

- Gong reports analysis of more than 30,000 prospecting emails across more than
  250 companies. Company-based personalization performed best for directors and
  above, while individual personalization performed better for less-senior
  personas. This supports role-aware, evidence-backed personalization rather
  than name insertion alone.
  [Gong personalization study](https://www.gong.io/blog/4-data-backed-ways-to-increase-your-email-reply-rate-and-book-that-meeting)
- Gong's analysis of 304,174 sales emails reports that an interest-oriented CTA
  outperformed immediate meeting requests in cold email. A newer executive
  analysis recommends offering a concrete piece of value rather than asking for
  calendar time.
  [Gong CTA analysis](https://www.gong.io/blog/this-surprising-cold-email-cta-will-help-you-book-a-lot-more-meetings),
  [Gong executive-email analysis](https://www.gong.io/blog/do-execs-really-reply-to-cold-email-here-s-what-the-data-says)
- The executive analysis reports better results for one-to-four-word subject
  lines and a 50-to-100-word body, while earlier Gong work used a broader
  30-to-150-word range. These should be initial test bands, not immutable truths.
- Gong's broader cold-email analysis associates unsupported ROI language,
  guilt-based follow-ups, and vague “thoughts?” CTAs with worse downstream
  outcomes. This aligns with the project's credibility and low-pressure rules.
  [Gong cold-email statistics](https://www.gong.io/blog/cold-email-stats)

Independent experiments support personalization as a useful principle but are
not direct B2B sales evidence:

- A quasi-randomized email invitation study found personalized greetings made
  recipients 1.5 times more likely to respond. The setting was research
  recruitment, so only the general personalization principle transfers.
  [BMC trial report](https://pmc.ncbi.nlm.nih.gov/articles/PMC4545569/)
- Three field experiments with 1,864 higher-education applicants found better
  response when tailoring used information voluntarily supplied by recipients;
  they also found a higher unsubscribe rate for customized email. This supports
  transparent, expected data use and argues against invasive personalization.
  [Journal of Research in Interactive Marketing study](https://www.sciencedirect.com/org/science/article/pii/S2040712221000840)
- A randomized trial of 1,943 physicians found no meaningful response lift from
  emphasizing an incentive in the subject line or changing Tuesday versus
  Friday delivery. Subject gimmicks and send-day folklore should not become
  training labels.
  [JMIR randomized trial](https://pmc.ncbi.nlm.nih.gov/articles/PMC5824098/)

## Proposed training-data composition

Start with a reviewable 600-to-1,000-row dataset rather than raw bulk ingestion.
The range is an engineering starting point, not a promised quality threshold.

| Slice | Target share | Purpose |
| --- | ---: | --- |
| Grounded positive outreach | 40% | Complete emails across products, ICPs, roles, evidence strengths, and safe abstentions. |
| Contrastive/adversarial pairs | 30% | Unsupported combinations, invented pain, false citations, fake offers, excessive claims, and corrected alternatives. |
| Project-specific CRM tool trajectories | 20% | Exact local CRM tools, authorization gates, clarification, no-op/refusal, state changes, and post-action summaries. |
| Follow-up and objection handling | 10% | Evidence-aware replies, respectful follow-ups, qualification, handoff, and opt-out handling. |

External rows should remain at or below 20% of training tokens until a measured
ablation demonstrates value. Every retained external row must be transformed,
content-hashed, attributed, license-recorded, split before generation, and
manually reviewed under the same rules as first-party synthetic rows.

### Coverage matrix

Each split should balance:

- at least five product categories and five ICP patterns;
- individual-contributor, manager, director, VP, and C-level roles;
- strong, weak, conflicting, stale, and absent prospect evidence;
- positive generation, `needs_more_evidence`, disqualification, and opt-out;
- initial outreach, follow-up, reply handling, CRM read, CRM write, and approval;
- supported single facts and adversarial fact combinations;
- organization identities disjoint across train, validation, and held-out sets.

## Proposed output contract changes

Global `claims_used` and `evidence_used` arrays prove only that identifiers
exist. They do not prove that citations support the actual sentence or that a
cited source was used. Replace them as the source of truth with a sentence-level
support map:

```json
{
  "generation_status": "drafted",
  "subject": "Weekly reporting",
  "body": "Northstar publicly describes weekly compliance reporting. FlowReport supports scheduled report generation and requires authorized access to source systems. Would scheduled report generation be relevant to your team?",
  "support_map": [
    {
      "sentence": "Northstar publicly describes weekly compliance reporting.",
      "claim_ids": [],
      "evidence_ids": ["evidence-case-reporting-regulated-1"]
    },
    {
      "sentence": "FlowReport supports scheduled report generation and requires authorized access to source systems.",
      "claim_ids": ["claim-report-schedule", "claim-report-access"],
      "evidence_ids": []
    },
    {
      "sentence": "Would scheduled report generation be relevant to your team?",
      "claim_ids": ["claim-report-schedule"],
      "evidence_ids": []
    }
  ],
  "uncertainty_notes": []
}
```

`claims_used` and `evidence_used`, if retained for reporting, should be derived
from `support_map`, not generated independently. When there is no meaningful,
safe personalization bridge, use `generation_status: "needs_more_evidence"`
instead of manufacturing relevance.

## Proposed hard gates

Any failure rejects the case regardless of style score:

1. **Contract:** exactly one valid object with approved fields and types.
2. **Known sources:** every support-map ID exists and is approved for this case.
3. **Citation precision:** every cited ID supports the sentence that cites it;
   unused citations fail.
4. **Citation recall:** every factual prospect statement has evidence support,
   and every product capability/outcome has approved-claim support.
5. **No unsupported combination:** two supported facts cannot be joined into a
   new causal, compatibility, deployment, or outcome claim without direct
   support. “Operates twelve hubs” plus “schedules reports” does not support
   “schedules reports across all twelve hubs.”
6. **Hypothesis discipline:** pain hypotheses remain possibilities or questions;
   they are never presented as known conditions.
7. **CTA integrity:** exactly one low-friction CTA; any offered audit, benchmark,
   sample, trial, or meeting must actually be approved and available.
8. **Control and safety:** disqualified, opted-out, unapproved, or
   insufficient-evidence cases abstain and never trigger sending or CRM writes.
9. **Bounds:** one-to-six subject words and 25-to-150 body words, with a target
   band of 50-to-100 words for executive first-touch email. Bounds remain
   configurable and should be validated empirically.

## Proposed human rubric

Score each dimension from 1 to 5 after all hard gates pass:

| Dimension | A score of 5 means |
| --- | --- |
| Personalization and relevance | Uses one or two meaningful, non-invasive, evidence-backed signals appropriate to the recipient's seniority. |
| Grounding and credibility | Every factual clause is traceable; uncertainty is honest; wording never becomes stronger than its source. |
| Clarity and concision | Easy to understand in one read, no filler, buzzwords, feature dump, or ambiguous pronouns. |
| Differentiation | Uses an approved capability that is relevant to the cited context without inventing an outcome. |
| CTA quality | One specific, low-pressure, truthful offer or interest question that is easy to answer. |
| Brand fit | Professional, respectful, human, and free from guilt, manipulation, fake familiarity, or exaggerated ROI. |

The next adapter should not pass quality review on `unchanged`. Proposed
acceptance requires:

- at least 95% valid structured output;
- zero unsupported claims, false citations, or unsafe actions;
- no held-out case regression on hard gates;
- blind human average of at least 4/5 with no dimension below 3;
- measurable improvement over the base model on the frozen held-out set; and
- a separate adversarial set that was never used to generate or select training
  examples.

## Next implementation sequence

1. Approve or revise this proposed rubric and support-map contract.
2. Add deterministic tests for citation precision/recall, abstention, CTA count,
   length bounds, and forbidden fact combinations.
3. Build a 60-to-100-case frozen benchmark before expanding training data.
4. Create and review the first 100-row balanced dataset slice.
5. Run a prompt-only baseline, then a small LoRA ablation using only that slice.
6. Expand toward 600-to-1,000 rows only if the ablation improves held-out
   quality without factuality regressions.

No dataset should be downloaded or added to training until its exact revision,
license text, provenance, and intended subset are approved.
