"""Build the deterministic, pending-review Phase 6 v2 candidate dataset."""

# Hand-authored sentence pools are kept readable as prose; other lint rules remain active.
# ruff: noqa: E501

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from src.evaluation.phase6_benchmark import load_phase6_benchmark
from src.evaluation.phase6_quality import evaluate_grounded_structure
from src.schemas.dataset import (
    ApprovedClaimRecord,
    DatasetCandidateManifestV2,
    EvidenceRecordV2,
    GenerationMethod,
    IdentityGroups,
    LicenseKind,
    TrainingExampleCandidateV2,
    TrainingInputV2,
    TrainingProvenanceCandidateV2,
)
from src.schemas.inference import (
    GroundedOutreachOutput,
    OutreachConstraints,
    SupportMapEntry,
)

OUTPUT_PATH = Path("configs/phase6/dataset-v2.candidate.json")
BENCHMARK_PATH = Path("configs/phase6/benchmark-v2.json")
COLLECTED_AT = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)

STATUS_COUNTS = {
    "train": {
        "drafted": 40,
        "needs_more_evidence": 24,
        "disqualified": 18,
        "opted_out": 18,
    },
    "validation": {
        "drafted": 10,
        "needs_more_evidence": 6,
        "disqualified": 4,
        "opted_out": 4,
    },
}
STATUSES = ("drafted", "needs_more_evidence", "disqualified", "opted_out")
ROLE_TIERS = ("individual_contributor", "manager", "director", "vp", "c_level")


@dataclass(frozen=True)
class ProductProfile:
    category: str
    name: str
    roles: tuple[tuple[str, str], ...]
    claims: tuple[str, str, str]
    hypotheses: tuple[str, ...]


PRODUCTS = (
    ProductProfile(
        "reporting_automation",
        "MetricMosaic",
        (
            ("individual_contributor", "Insights Analyst"),
            ("manager", "Reporting Manager"),
            ("director", "Director of Business Intelligence"),
            ("vp", "VP of Analytics"),
            ("c_level", "Chief Data Officer"),
        ),
        (
            "assembles scheduled operating reports from approved systems",
            "preserves source references beside each report section",
            "supports a time-boxed reporting workflow evaluation",
        ),
        (
            "Recurring scorecard preparation may consume analyst time.",
            "Different reporting owners might create review handoffs.",
            "Leaders could wait for consistent source-backed reporting.",
            "Manual commentary may make weekly performance packs harder to reconcile.",
            "A growing reporting calendar could crowd out analysis for the BI team.",
            "Unclear source ownership might slow sign-off on executive updates.",
            "A wider stakeholder circle may make commentary consistency difficult to maintain.",
            "The reporting queue could grow faster than the team can validate its inputs.",
            "A new reporting stakeholder may add another layer to the review calendar.",
            "The team might spend more time explaining variance than acting on it.",
        ),
    ),
    ProductProfile(
        "security_asset_inventory",
        "CloudLedger",
        (
            ("individual_contributor", "Cloud Security Specialist"),
            ("manager", "Security Operations Manager"),
            ("director", "Director of Security Architecture"),
            ("vp", "VP of Cybersecurity"),
            ("c_level", "Chief Security Officer"),
        ),
        (
            "maps assets across approved cloud accounts",
            "records observation time and source for each asset",
            "supports a time-boxed asset review workflow evaluation",
        ),
        (
            "Cloud growth may make asset ownership harder to verify.",
            "Distributed account ownership might slow inventory reconciliation.",
            "Newly observed resources could add repeated review work.",
            "A changing account footprint may leave security teams chasing stale registers.",
            "Unclear ownership could delay triage when a new asset appears.",
            "Frequent cloud changes might make quarterly attestations laborious.",
            "A new service boundary may create gaps between inventory and ownership review.",
            "Security teams could lose time deciding which account should answer an asset question.",
            "A larger inventory may make ownership exceptions harder to resolve quickly.",
            "The control process could become reactive when new resources arrive between reviews.",
        ),
    ),
    ProductProfile(
        "developer_productivity",
        "LoopSignal",
        (
            ("individual_contributor", "Developer Productivity Engineer"),
            ("manager", "Engineering Productivity Manager"),
            ("director", "Director of Developer Infrastructure"),
            ("vp", "VP of Platform Engineering"),
            ("c_level", "Chief Engineering Officer"),
        ),
        (
            "groups recurring CI failure patterns from approved repositories",
            "links failure summaries to their source builds",
            "supports a time-boxed developer workflow evaluation",
        ),
        (
            "Repeated build failures may draw engineers into triage.",
            "Multiple repository owners might fragment failure analysis.",
            "Unresolved CI patterns could slow delivery feedback.",
            "A busy release cadence may hide recurring failures in ticket queues.",
            "Scattered build context could make platform follow-up less consistent.",
            "Longer triage loops might reduce confidence in the delivery signal.",
            "A growing build surface may make it harder to distinguish systemic failures from noise.",
            "Platform leaders could need a clearer view before investing in another CI improvement.",
            "A broader repository estate may make failure trends harder to compare consistently.",
            "The engineering team could spend valuable focus separating repeated defects from one-offs.",
        ),
    ),
    ProductProfile(
        "support_knowledge_workflow",
        "GuideCurrent",
        (
            ("individual_contributor", "Knowledge Operations Specialist"),
            ("manager", "Support Enablement Manager"),
            ("director", "Director of Customer Education"),
            ("vp", "VP of Support Experience"),
            ("c_level", "Chief Customer Experience Officer"),
        ),
        (
            "searches approved knowledge sources for support teams",
            "keeps source references beside suggested answers",
            "supports a time-boxed knowledge workflow evaluation",
        ),
        (
            "Several knowledge sources may make answer consistency harder.",
            "Frequent article changes might complicate support verification.",
            "Low-confidence questions could require repeated escalation.",
            "A distributed support team may spend time checking which article is current.",
            "Unclear source ownership could make coaching conversations less concrete.",
            "A rising question backlog might expose gaps between policy and practice.",
            "Support leaders may struggle to tell whether an answer gap is editorial or operational.",
            "A broader service catalog could make knowledge ownership harder to keep visible.",
            "Support managers may need a more reliable signal before changing article priorities.",
            "A growing set of customer questions could make informal knowledge sharing fragile.",
        ),
    ),
    ProductProfile(
        "crm_data_hygiene",
        "RecordBeacon",
        (
            ("individual_contributor", "Revenue Systems Analyst"),
            ("manager", "Revenue Systems Manager"),
            ("director", "Director of Commercial Operations"),
            ("vp", "VP of Revenue Systems"),
            ("c_level", "Chief Commercial Officer"),
        ),
        (
            "checks required CRM fields before approved updates",
            "flags possible duplicate records for human review",
            "supports a time-boxed CRM workflow evaluation",
        ),
        (
            "Repeated CRM checks may affect confidence in pipeline reporting.",
            "Potential duplicates might require recurring human review.",
            "Field validation could add manual steps before approved changes.",
            "A larger account base may make duplicate review harder to keep timely.",
            "Inconsistent field ownership could weaken confidence in forecast views.",
            "Manual exception handling might pull revenue systems staff into cleanup work.",
            "A changing sales process may make field ownership harder to enforce consistently.",
            "Revenue leaders could hesitate to trust a forecast built on unresolved record issues.",
            "A more complex territory model may increase the cost of resolving record exceptions.",
            "The operations team could lose reporting time when cleanup decisions remain ambiguous.",
        ),
    ),
)

COMPANIES = (
    "Northwind Freight",
    "Cobalt Health Partners",
    "Harborstone Foods",
    "Juniper Ridge Energy",
    "Silverline Manufacturing",
    "Maple Crest Bank",
    "Redwood Learning Group",
    "Summit Field Services",
    "Bluewater Insurance",
    "Ironwood Logistics",
    "Brightwell Clinics",
    "Pinehaven Retail",
    "Crescent BioSystems",
    "Granite Peak Software",
    "Willow Creek Utilities",
    "Oakline Hospitality",
    "Lighthouse Materials",
    "Evergreen Mobility",
    "Atlas Community Care",
    "Meadowlark Media",
    "Clearbrook Payments",
    "Stonebridge Construction",
    "Riverside Equipment",
    "Highland Marketplaces",
    "Westhaven Legal",
    "Orchard Street Capital",
    "Frostline Travel",
    "Beacon Hill Telecom",
    "Golden Prairie Agriculture",
    "Cedarworks Housing",
    "Aspen Grove Pharma",
    "Mariner Port Services",
    "Copperleaf Security",
    "Elm Street Education",
    "Rainier Outdoor Goods",
    "Sagebrush Clinical",
    "Brookfield Design",
    "Tidewater Marine",
    "Prairie Star Foods",
    "Hawthorne Automotive",
    "Linden Public Media",
    "Mosaic Supply Co",
    "Fairview Diagnostics",
    "Canyon Creek Mining",
    "Rosewood Financial",
    "Bayside Consumer Goods",
    "Timberline Data",
    "Suncrest Aviation",
    "Parkside Wellness",
    "Blue Ridge Components",
    "Windward Commerce",
)

OPENING_FORMS = (
    "Your public operations page mentions {signal}.",
    "I saw that {company} describes {signal} in its operating materials.",
    "The way {company} talks about {signal} caught my attention.",
    "Your team appears to be coordinating {signal}, based on the public role brief.",
    "I noticed a public reference to {signal} at {company}.",
    "The public process note from {company} points to {signal}.",
    "Your recent operating language suggests the team is managing {signal}.",
    "I was looking at {company}'s public materials and found {signal}.",
    "The role description I read connects {company} with {signal}.",
    "A public team update makes {signal} visible at {company}.",
    "Your published workflow describes how the team handles {signal}.",
    "I noticed {signal} while reviewing {company}'s public operating context.",
    "The public evidence around {company} includes {signal}.",
    "Your operating guide gives a useful view of {signal}.",
    "A public hiring page suggests that {company} is working through {signal}.",
    "The workflow language on your site highlights {signal}.",
    "I came across a clear reference to {signal} in {company}'s public information.",
    "Your team page places {signal} close to the day-to-day workflow.",
    "The public record suggests that {company} is keeping an eye on {signal}.",
    "I noticed the team is accountable for {signal}, from the public role details.",
    "The operating context around {company} includes a focus on {signal}.",
    "Your public materials make the work behind {signal} especially clear.",
    "The role context at {company} appears connected to {signal}.",
    "I found a useful public signal about {signal} at {company}.",
    "The published workflow at {company} has a visible thread around {signal}.",
)

PRODUCT_CLAIM_FORMS = (
    "{product} {claim}.",
    "Teams use {product} when it {claim}.",
    "The useful part of {product} is that it {claim}.",
    "With {product}, the workflow {claim}.",
    "{product} gives operators a way to see how it {claim}.",
    "The {product} approach is designed around a workflow that {claim}.",
    "For this kind of work, {product} is useful because it {claim}.",
    "{product} keeps the process focused while it {claim}.",
    "One practical capability in {product} is that it {claim}.",
    "{product} brings a structured workflow where it {claim}.",
    "The product is built so {product} can support a process where it {claim}.",
    "{product} helps a team work with a process that {claim}.",
    "A team evaluating {product} can see how it {claim}.",
    "{product} is useful when a team needs a workflow that {claim}.",
    "The operating value of {product} starts with the fact that it {claim}.",
    "{product} makes the workflow easier because it {claim}.",
    "The core workflow in {product} gives teams a view as it {claim}.",
    "{product} gives the owner a clear view when it {claim}.",
    "A grounded use of {product} is a workflow where it {claim}.",
    "{product} can fit beside an existing process while it {claim}.",
    "The {product} workflow helps teams by ensuring it {claim}.",
    "{product} is aimed at teams whose workflow needs a system that {claim}.",
    "One way {product} supports operators is because it {claim}.",
    "{product} turns the approved workflow into a process where it {claim}.",
    "The clearest product fit is when {product} {claim}.",
)

CTA_FORMS = (
    (
        "Would it be useful to compare how your team handles this today?",
        "interest_question",
    ),
    (
        "Is this a workflow you are considering improving this quarter?",
        "interest_question",
    ),
    (
        "Would a brief exchange on the current process be worthwhile?",
        "interest_question",
    ),
    ("Could I ask how the team reviews this work today?", "interest_question"),
    (
        "Would you be open to sharing where this process feels most manual?",
        "interest_question",
    ),
    ("Is there a clear owner for this workflow on your side?", "interest_question"),
    (
        "Would a short conversation help test whether this is relevant?",
        "interest_question",
    ),
    (
        "How are you thinking about this workflow as the team grows?",
        "interest_question",
    ),
    ("Would it make sense to trade notes on the review handoff?", "interest_question"),
    (
        "Could we compare the signal you use to decide when follow-up is needed?",
        "interest_question",
    ),
    (
        "Is this pain visible enough internally to merit a closer look?",
        "interest_question",
    ),
    (
        "Would you be interested in a practical example from a similar workflow?",
        "interest_question",
    ),
    ("Can I learn how your team keeps this information current?", "interest_question"),
    (
        "Would a quick discussion of the operating tradeoffs be useful?",
        "interest_question",
    ),
    (
        "Do you have a preferred way to validate this kind of change?",
        "interest_question",
    ),
    (
        "Would it help to map the current handoff before discussing tools?",
        "interest_question",
    ),
    (
        "Is someone already reviewing whether this process scales cleanly?",
        "interest_question",
    ),
    (
        "Could a short conversation clarify whether this belongs on your roadmap?",
        "interest_question",
    ),
    (
        "Would you like to compare the evidence your team relies on?",
        "interest_question",
    ),
    (
        "How does the team decide which exceptions deserve attention?",
        "interest_question",
    ),
    ("Would a time-boxed evaluation of this workflow be useful?", "approved_offer"),
    (
        "Could I offer a short, reviewable evaluation for the team to consider?",
        "approved_offer",
    ),
    ("Would an approved pilot conversation help you assess the fit?", "approved_offer"),
    ("Is a small evaluation of the workflow worth exploring?", "approved_offer"),
    (
        "Would you consider a focused evaluation before changing the process?",
        "approved_offer",
    ),
    (
        "Could we set up a bounded evaluation if the workflow is a priority?",
        "approved_offer",
    ),
    (
        "Would a short review of the approved workflow help your team decide?",
        "approved_offer",
    ),
    (
        "Is there value in evaluating this against one current process?",
        "approved_offer",
    ),
    (
        "Would you be open to a limited workflow evaluation with clear guardrails?",
        "approved_offer",
    ),
    (
        "Could an approved evaluation give you a concrete starting point?",
        "approved_offer",
    ),
)

ABSTENTION_RATIONALES = {
    "needs_more_evidence": (
        "The only signal is a light role mention, so there is not enough evidence to personalize responsibly.",
        "The available process note is fourteen months old, which makes the current workflow uncertain.",
        "Two public sources describe the ownership differently, so the operating context needs clarification.",
        "No prospect evidence was found for this workflow, so a grounded message would be speculative.",
        "The public material hints at the problem but does not establish that it is active now.",
        "The role language suggests involvement without showing that this person owns the decision.",
        "The source is too general to connect the company’s work to this product category.",
        "The evidence describes a past process, not a current priority, so outreach should wait.",
        "The sources disagree about team ownership and need a human reconciliation first.",
        "A single indirect mention does not support a confident pain hypothesis for this prospect.",
        "The available evidence lacks a current operational detail that would make personalization credible.",
        "The public signal is plausible but too thin to justify a specific outreach claim.",
        "The source identifies a possible issue but not the person or team accountable for it.",
        "The available evidence does not establish enough current context for a respectful message.",
        "The public wording is suggestive, but the underlying workflow remains unverified.",
        "A human reviewer would need one more current source before approving personalization.",
    ),
    "disqualified": (
        "The company states that this workflow is owned by a parent organization, so the prospect is outside scope.",
        "The reviewed profile says the business does not operate the relevant system internally.",
        "The public operating model routes this work through channel partners rather than an internal team.",
        "The company’s technology note shows an exclusively on-premise estate, which rules out this fit.",
        "The organization has no in-house engineering function for the workflow described here.",
        "The sales model keeps the relevant records with distributors, so this team cannot own the process.",
        "The support model is partner-led and does not expose the direct workflow this product serves.",
        "The reviewed architecture explicitly excludes the connected systems required for this use case.",
        "The company’s operating profile assigns the process to an external service provider.",
        "The prospect profile lacks the internal function needed to act on this workflow.",
        "The public business model places the relevant data outside the prospect’s control.",
        "The current operating structure makes this category of workflow irrelevant to the prospect.",
        "The reviewed account structure places this work in a separate business that is not the target.",
        "The public service model does not contain the operational team this product requires.",
        "The prospect lacks the approved system boundary needed for a responsible introduction.",
        "The company’s stated scope excludes the workflow represented by this product.",
    ),
    "opted_out": (
        "A prior reply explicitly asked the sender not to email again, so outreach permission is withdrawn.",
        "The contact preference record marks sales email as do not contact.",
        "The latest consent entry records that email permission was withdrawn.",
        "The company’s preference center lists this contact as opted out of sales outreach.",
        "A previous message requests no further contact from vendors.",
        "The recorded communication preference blocks promotional email to this prospect.",
        "The prospect has withdrawn permission for follow-up messages, regardless of product fit.",
        "The consent history indicates that another outreach attempt would ignore a clear opt-out.",
        "The contact’s stated preference is not to receive additional sales correspondence.",
        "The organization’s suppression record blocks this type of outreach.",
        "A direct no-contact instruction takes precedence over any potentially relevant signal.",
        "The current preference record does not authorize another sales conversation.",
        "The contact’s latest instruction prohibits another product-related message.",
        "The recorded consent state requires this prospect to remain suppressed.",
        "The prior response closes the channel for additional vendor follow-up.",
        "The outreach policy for this contact does not permit a new introduction.",
    ),
}


def _claims(profile: ProductProfile) -> list[ApprovedClaimRecord]:
    category_id = profile.category.replace("_", "-")
    return [
        ApprovedClaimRecord(
            claim_id=f"claim-candidate-{category_id}-{position + 1:02d}",
            text=f"{profile.name} {text}.",
            source_kind="first_party_synthetic",
            source_reference=f"candidate-product-profile-{profile.category}",
            license_kind=LicenseKind.SYNTHETIC,
            license_basis="Project-owned controlled candidate dataset claim",
        )
        for position, text in enumerate(profile.claims)
    ]


def _evidence(
    index: int, condition: str, company: str, status: str
) -> list[EvidenceRecordV2]:
    if status == "disqualified":
        texts = (
            "The parent organization prepares all recurring reports for this business.",
            "The reviewed profile states that the company has no internal CRM system.",
            "The operating model routes customer support through channel partners.",
            "The architecture note describes an exclusively on-premise estate.",
            "The company profile shows no in-house software engineering team.",
            "Customer records remain with distributors rather than this sales team.",
        )
        text = texts[index % len(texts)]
    elif status == "opted_out":
        texts = (
            "A prior reply asks the sender not to email again.",
            "The contact preference record marks sales email as do not contact.",
            "The latest consent entry records email permission as withdrawn.",
            "The preference center lists this contact as opted out of sales outreach.",
            "A previous message requests no further contact from vendors.",
            "The communication record blocks promotional email to this prospect.",
        )
        text = texts[index % len(texts)]
    elif condition == "absent":
        text = None
    else:
        texts = {
            "strong": (
                "recurring cross-team review across regional operations",
                "leaders reconciling recurring operating updates",
                "ownership for a recurring operational review",
                "source-backed review handoffs across teams",
                "a recurring queue of operational checks",
            ),
            "weak": (
                "assistance with periodic process review in an analyst role",
                "support for recurring team updates in a hiring brief",
                "exposure to periodic operational checks in one role",
                "help maintaining the review process in a public job post",
                "light involvement with recurring review work",
            ),
            "conflicting": (
                "central and regional teams both claiming process ownership",
                "one policy owner and a later regional responsibility assignment",
                "disagreement between central and local workflow ownership",
                "different process owners named in the operating guide and role post",
                "conflicting public descriptions of recurring review ownership",
            ),
            "stale": (
                "a recurring review reference collected fourteen months ago",
                "the most recent accessible workflow reference collected fourteen months ago",
                "a dated operating page with no current source",
                "workflow evidence collected fourteen months ago",
                "an older role brief without current confirmation",
            ),
        }[condition]
        text = texts[index % len(texts)]
    if text is None:
        return []
    return [
        EvidenceRecordV2(
            evidence_id=f"evidence-candidate-{index:03d}-01",
            text=text,
            source_url=f"https://example.com/candidate/source-{index:03d}",
            collected_at=datetime(2022, 1, 15, tzinfo=UTC)
            if condition == "stale"
            else COLLECTED_AT,
            content_sha256=sha256(text.encode("utf-8")).hexdigest(),
            source_kind="first_party_synthetic",
            source_reference=f"candidate-company-source-{index:03d}-01",
            license_kind=LicenseKind.SYNTHETIC,
            license_basis="Project-owned controlled candidate dataset evidence",
        )
    ]


SUBJECT_FORMS = (
    "Workflow question for {company}",
    "Review idea for {company}",
    "Next step for {company}",
    "Traceability for {company}",
    "Operations thought for {company}",
    "Process question for {company}",
    "Workflow note for {company}",
    "Handoff question for {company}",
    "Review path for {company}",
    "Notes on {company}",
)

COMPACT_LABELS = {
    "reporting_automation": ("reporting", "MetricMosaic tracks sources."),
    "security_asset_inventory": ("security", "CloudLedger logs assets."),
    "developer_productivity": ("delivery", "LoopSignal links builds."),
    "support_knowledge_workflow": ("support", "GuideCurrent cites sources."),
    "crm_data_hygiene": ("CRM", "RecordBeacon flags duplicates."),
}


def _draft(
    profile: ProductProfile,
    claims: list[ApprovedClaimRecord],
    evidence: list[EvidenceRecordV2],
    row_index: int,
    company: str,
) -> GroundedOutreachOutput:
    evidence_id = evidence[0].evidence_id
    claim_ids = sorted(claim.claim_id for claim in claims)
    compact = row_index % 11 == 0
    entries_by_shape = (
        ("prospect_fact", "product_claim", "cta"),
        ("prospect_fact", "product_claim", "hypothesis", "cta"),
        ("prospect_fact", "hypothesis", "product_claim", "cta"),
        ("prospect_fact", "product_claim", "product_claim", "hypothesis", "cta"),
        ("prospect_fact", "hypothesis", "hypothesis", "product_claim", "cta"),
        ("prospect_fact", "product_claim", "hypothesis", "product_claim", "cta"),
        ("prospect_fact", "prospect_fact", "product_claim", "hypothesis", "cta"),
        (
            "prospect_fact",
            "hypothesis",
            "product_claim",
            "product_claim",
            "hypothesis",
            "cta",
        ),
    )
    shape = entries_by_shape[row_index % len(entries_by_shape)]
    entries: list[SupportMapEntry] = []
    for position, role in enumerate(shape):
        if role == "prospect_fact":
            sentence = OPENING_FORMS[
                (row_index + position + 3) % len(OPENING_FORMS)
            ].format(company=company, signal=evidence[0].text.rstrip(".").lower())
            entries.append(
                SupportMapEntry(
                    sentence=sentence, role=role, evidence_ids=[evidence_id]
                )
            )
        elif role == "product_claim":
            claim_position = (row_index + position) % len(profile.claims)
            sentence = PRODUCT_CLAIM_FORMS[
                (row_index + position) % len(PRODUCT_CLAIM_FORMS)
            ].format(product=profile.name, claim=profile.claims[claim_position])
            entries.append(
                SupportMapEntry(
                    sentence=sentence, role=role, claim_ids=[claim_ids[claim_position]]
                )
            )
        elif role == "hypothesis":
            entries.append(
                SupportMapEntry(
                    sentence=profile.hypotheses[
                        (row_index + position) % len(profile.hypotheses)
                    ],
                    role=role,
                )
            )
        else:
            cta_sentence, cta_kind = CTA_FORMS[row_index % len(CTA_FORMS)]
            cta_claim = (
                claim_ids[2]
                if cta_kind == "approved_offer"
                else claim_ids[(row_index + 1) % 3]
            )
            entries.append(
                SupportMapEntry(
                    sentence=cta_sentence,
                    role=role,
                    claim_ids=[cta_claim],
                    cta_kind=cta_kind,
                )
            )
    if row_index % 7 == 0:
        entries.insert(
            1,
            SupportMapEntry(
                sentence=OPENING_FORMS[(row_index + 11) % len(OPENING_FORMS)].format(
                    company=company, signal=evidence[0].text.rstrip(".").lower()
                ),
                role="prospect_fact",
                evidence_ids=[evidence_id],
            ),
        )
        entries.insert(
            3,
            SupportMapEntry(
                sentence=PRODUCT_CLAIM_FORMS[
                    (row_index + 9) % len(PRODUCT_CLAIM_FORMS)
                ].format(product=profile.name, claim=profile.claims[0]),
                role="product_claim",
                claim_ids=[claim_ids[0]],
            ),
        )
        entries.insert(
            -1,
            SupportMapEntry(
                sentence=profile.hypotheses[(row_index + 2) % len(profile.hypotheses)],
                role="hypothesis",
            ),
        )
    current_words = len(
        re.findall(r"\b[\w'-]+\b", " ".join(entry.sentence for entry in entries))
    )
    if not compact and row_index % 3 == 0 and current_words < 100:
        additions = (
            "prospect_fact",
            "product_claim",
            "hypothesis",
            "product_claim",
        )
        for position, role in enumerate(additions):
            if role == "prospect_fact":
                sentence = OPENING_FORMS[
                    (row_index + position + 17) % len(OPENING_FORMS)
                ].format(company=company, signal=evidence[0].text.rstrip(".").lower())
                entry = SupportMapEntry(
                    sentence=sentence, role=role, evidence_ids=[evidence_id]
                )
            elif role == "product_claim":
                claim_position = (row_index + position + 1) % len(profile.claims)
                sentence = PRODUCT_CLAIM_FORMS[
                    (row_index + position + 13) % len(PRODUCT_CLAIM_FORMS)
                ].format(product=profile.name, claim=profile.claims[claim_position])
                entry = SupportMapEntry(
                    sentence=sentence, role=role, claim_ids=[claim_ids[claim_position]]
                )
            else:
                entry = SupportMapEntry(
                    sentence=profile.hypotheses[
                        (row_index + position + 3) % len(profile.hypotheses)
                    ],
                    role=role,
                )
            entry_words = len(re.findall(r"\b[\w'-]+\b", entry.sentence))
            if current_words + entry_words <= 145:
                entries.insert(-1, entry)
                current_words += entry_words
    if compact:
        if row_index % 5 == 0:
            cta_sentence, cta_kind = (
                "Would a bounded evaluation help?",
                "approved_offer",
            )
        else:
            cta_sentence, cta_kind = "Worth comparing notes?", "interest_question"
        cta_claim = claim_ids[2] if cta_kind == "approved_offer" else claim_ids[1]
        compact_label, compact_claim = COMPACT_LABELS[profile.category]
        entries = [
            SupportMapEntry(
                sentence=f"Your team reviews {compact_label} work.",
                role="prospect_fact",
                evidence_ids=[evidence_id],
            ),
            SupportMapEntry(
                sentence=f"The {compact_label} workflow recurs.",
                role="prospect_fact",
                evidence_ids=[evidence_id],
            ),
            SupportMapEntry(
                sentence=compact_claim,
                role="product_claim",
                claim_ids=[claim_ids[1]],
            ),
            SupportMapEntry(
                sentence=f"{compact_label.capitalize()} review might recur often.",
                role="hypothesis",
            ),
            SupportMapEntry(
                sentence=f"{compact_label.capitalize()} work may persist weekly.",
                role="hypothesis",
            ),
            SupportMapEntry(
                sentence=cta_sentence,
                role="cta",
                claim_ids=[cta_claim],
                cta_kind=cta_kind,
            ),
        ]
    seen_sentences: set[str] = set()
    for entry_index, entry in enumerate(entries):
        if entry.sentence in seen_sentences and entry.role == "hypothesis":
            replacement = next(
                hypothesis
                for offset in range(len(profile.hypotheses))
                for hypothesis in (
                    profile.hypotheses[(row_index + offset) % len(profile.hypotheses)],
                )
                if hypothesis not in seen_sentences
            )
            entries[entry_index] = entry.model_copy(update={"sentence": replacement})
        if entries[entry_index].sentence in seen_sentences:
            raise AssertionError("draft support map sentence was reused")
        seen_sentences.add(entries[entry_index].sentence)
    return GroundedOutreachOutput(
        generation_status="drafted",
        subject=SUBJECT_FORMS[row_index % len(SUBJECT_FORMS)].format(company=company),
        body=" ".join(entry.sentence for entry in entries),
        support_map=entries,
    )


def _output(
    profile: ProductProfile,
    claims: list[ApprovedClaimRecord],
    evidence: list[EvidenceRecordV2],
    status: str,
    index: int,
    company: str,
) -> GroundedOutreachOutput:
    if status == "drafted":
        return _draft(profile, claims, evidence, index, company)
    rationale = ABSTENTION_RATIONALES[status][
        index % len(ABSTENTION_RATIONALES[status])
    ]
    return GroundedOutreachOutput(
        generation_status=status,
        subject="",
        body="",
        uncertainty_notes=[f"{company}: {rationale}"],
    )


def _pair_specs() -> list[tuple[str, str, str]]:
    kinds = [
        ("strong", "absent", "opted_out"),
        ("strong", "absent", "disqualified"),
        ("strong", "stale", "needs_more_evidence"),
        ("strong", "conflicting", "needs_more_evidence"),
        ("strong", "absent", "needs_more_evidence"),
    ]
    return [kinds[index % len(kinds)] for index in range(15)]


def _normalized_sentence(sentence: str) -> str:
    normalized = sentence.casefold()
    replacement_names = [
        *sorted(COMPANIES, key=len, reverse=True),
        *sorted((profile.name for profile in PRODUCTS), key=len, reverse=True),
        *sorted(
            (role for profile in PRODUCTS for _, role in profile.roles),
            key=len,
            reverse=True,
        ),
    ]
    for name in replacement_names:
        normalized = normalized.replace(name.casefold(), "<entity>")
    return re.sub(r"[^a-z0-9<>\s]", "", normalized).strip()


def _assert_content_diversity(rows: list[TrainingExampleCandidateV2]) -> None:
    outputs = [row.proposed_output for row in rows]
    drafted = [output for output in outputs if output.generation_status == "drafted"]
    abstentions = [
        output for output in outputs if output.generation_status != "drafted"
    ]
    subjects_and_notes = [output.subject for output in outputs]
    subjects_and_notes.extend(
        note for output in outputs for note in output.uncertainty_notes
    )
    if any(
        any(character.isdigit() for character in text) for text in subjects_and_notes
    ):
        raise AssertionError("subject or uncertainty note contains a digit")
    for row in rows:
        evidence_by_id = {
            item.evidence_id: item.text for item in row.input.prospect_evidence
        }
        for entry in row.proposed_output.support_map:
            for digit_sequence in re.findall(r"\d+", entry.sentence):
                cited_text = " ".join(
                    evidence_by_id[evidence_id]
                    for evidence_id in entry.evidence_ids
                    if evidence_id in evidence_by_id
                )
                if digit_sequence not in cited_text:
                    raise AssertionError(
                        "body digit is not present in the cited evidence text"
                    )
    forbidden = re.compile(
        r"(?i)\b(row|case|example|candidate)\s*\d|\bcandidate company\b"
    )
    output_text = json.dumps([output.model_dump(mode="json") for output in outputs])
    if forbidden.search(output_text):
        raise AssertionError("proposed output contains a placeholder marker")
    sentence_counts = Counter(
        _normalized_sentence(entry.sentence)
        for output in drafted
        for entry in output.support_map
    )
    if max(sentence_counts.values(), default=0) > 4:
        raise AssertionError(
            "normalized sentence reuse exceeds four rows: "
            f"distinct={len(sentence_counts)}, "
            f"max_reuse={max(sentence_counts.values(), default=0)}, "
            f"examples={sentence_counts.most_common(3)}"
        )
    cta_counts = Counter(
        entry.sentence
        for output in drafted
        for entry in output.support_map
        if entry.role == "cta"
    )
    if len(cta_counts) < 20 or max(cta_counts.values(), default=0) > 4:
        raise AssertionError("CTA diversity threshold failed")
    rationale_counts = Counter(
        _normalized_sentence(note)
        for output in abstentions
        for note in output.uncertainty_notes
    )
    if len(rationale_counts) < 30 or max(rationale_counts.values(), default=0) > 4:
        raise AssertionError(
            "abstention rationale diversity threshold failed: "
            f"distinct={len(rationale_counts)}, max_reuse={max(rationale_counts.values(), default=0)}"
        )
    shapes = Counter(
        tuple(entry.role for entry in output.support_map) for output in drafted
    )
    if len(shapes) < 6 or max(shapes.values(), default=0) > len(drafted) * 0.4:
        raise AssertionError("support-map role-shape diversity threshold failed")
    body_counts = [len(re.findall(r"\b[\w'-]+\b", output.body)) for output in drafted]
    if (
        sum(50 <= count <= 100 for count in body_counts) < 20
        or sum(count > 100 for count in body_counts) < 6
        or min(body_counts, default=0) > 25
        or max(body_counts, default=0) < 130
    ):
        raise AssertionError(
            "draft body length spread threshold failed: "
            f"band={sum(50 <= count <= 100 for count in body_counts)}, "
            f"above={sum(count > 100 for count in body_counts)}, "
            f"min={min(body_counts, default=0)}, max={max(body_counts, default=0)}"
        )
    company_names = {
        name
        for row in rows
        for name in COMPANIES
        if name in json.dumps(row.proposed_output.model_dump(mode="json"))
    }
    if len(company_names) < 40:
        raise AssertionError("company name diversity threshold failed")
    if len({row.input.target_role for row in rows}) < 20:
        raise AssertionError(
            "target role diversity threshold failed: "
            f"distinct={len({row.input.target_role for row in rows})}"
        )


def _make_row(
    index: int,
    split: str,
    status: str,
    profile: ProductProfile,
    condition: str,
    *,
    pair_index: int | None = None,
) -> TrainingExampleCandidateV2:
    company_number = (
        f"{pair_index + 1:02d}" if pair_index is not None else f"{index:03d}"
    )
    company = COMPANIES[
        pair_index if pair_index is not None else (index - 1) % len(COMPANIES)
    ]
    identity_index = pair_index if pair_index is not None else index // len(PRODUCTS)
    evidence_index = pair_index + 1 if pair_index is not None else index
    claims = _claims(profile)
    evidence = _evidence(evidence_index, condition, company, status)
    inputs = TrainingInputV2(
        target_role=profile.roles[identity_index % len(profile.roles)][1],
        approved_claims=claims,
        prospect_evidence=evidence,
        pain_hypotheses=[profile.hypotheses[index % len(profile.hypotheses)]],
        constraints=OutreachConstraints(),
    )
    output = _output(profile, claims, evidence, status, index, company)
    report = evaluate_grounded_structure(
        output,
        approved_claim_ids={claim.claim_id for claim in claims},
        approved_evidence_ids={item.evidence_id for item in evidence},
        constraints=inputs.constraints,
    )
    if not report.passed:
        raise AssertionError(
            f"candidate row {index} failed structural gate: {report.violations}"
        )
    return TrainingExampleCandidateV2(
        example_id=f"dataset-example-candidate-{index:03d}",
        schema_version="2.0",
        task_type="outreach_generation",
        intended_split=split,
        scenario_kind="initial_outreach" if index % 2 else "follow_up",
        product_name=profile.name,
        identity_groups=IdentityGroups(
            product_group=(
                f"product-candidate-{split}-{profile.category.replace('_', '-')}"
            ),
            icp_group=(
                f"candidate_{split}_icp_"
                f"{(pair_index if pair_index is not None else index) % 5}"
            ),
            company_group=f"company-candidate-{company_number}",
            prospect_group=f"prospect-candidate-{company_number}",
        ),
        prompt_template_version="phase6-candidate-v2",
        input=inputs,
        proposed_output=output,
        provenance=TrainingProvenanceCandidateV2(
            source_kind="synthetic_controlled",
            source_reference="phase6-dataset-v2-builder",
            license_kind=LicenseKind.SYNTHETIC,
            license_basis="Project-owned deterministic candidate dataset",
            generation_method=GenerationMethod.HUMAN_AUTHORED,
        ),
        gate_report=report,
    )


def build_candidate_manifest() -> DatasetCandidateManifestV2:
    benchmark = load_phase6_benchmark(BENCHMARK_PATH)
    benchmark_groups = {
        group
        for case in benchmark.cases
        for group in case.identity_groups.model_dump().values()
    }
    rows: list[TrainingExampleCandidateV2] = []
    index = 1
    pair_specs = _pair_specs()
    for pair_index, (left_condition, right_condition, non_draft_status) in enumerate(
        pair_specs
    ):
        split = "train" if pair_index < 8 else "validation"
        profile = PRODUCTS[pair_index % len(PRODUCTS)]
        rows.append(
            _make_row(
                index, split, "drafted", profile, left_condition, pair_index=pair_index
            )
        )
        index += 1
        rows.append(
            _make_row(
                index,
                split,
                non_draft_status,
                profile,
                right_condition,
                pair_index=pair_index,
            )
        )
        index += 1

    for split, counts in STATUS_COUNTS.items():
        existing = sum(1 for row in rows if row.intended_split == split)
        for status in STATUSES:
            needed = counts[status] - sum(
                row.intended_split == split
                and row.proposed_output.generation_status == status
                for row in rows
            )
            for _ in range(needed):
                profile = PRODUCTS[(index + len(split)) % len(PRODUCTS)]
                condition = ("strong", "weak", "conflicting", "stale", "absent")[
                    index % 5
                ]
                if status == "drafted":
                    condition = "strong" if index % 2 else "weak"
                if status == "disqualified":
                    condition = "strong"
                if status == "opted_out":
                    condition = "strong" if index % 2 else "absent"
                rows.append(_make_row(index, split, status, profile, condition))
                index += 1
        if (
            len([row for row in rows if row.intended_split == split])
            != counts["drafted"]
            + counts["needs_more_evidence"]
            + counts["disqualified"]
            + counts["opted_out"]
        ):
            raise AssertionError(
                f"row count drifted for {split}; started with {existing}"
            )

    distribution = {
        split: {
            status: sum(
                row.intended_split == split
                and row.proposed_output.generation_status == status
                for row in rows
            )
            for status in STATUSES
        }
        for split in STATUS_COUNTS
    }
    if distribution != STATUS_COUNTS:
        raise AssertionError(f"unexpected candidate distribution: {distribution}")
    if len(rows) != 124:
        raise AssertionError(f"expected 124 rows, got {len(rows)}")
    identities = [
        group for row in rows for group in row.identity_groups.model_dump().values()
    ]
    if benchmark_groups.intersection(identities):
        raise AssertionError("candidate identity overlaps frozen benchmark")
    group_splits: dict[str, set[str]] = {}
    for row in rows:
        for group in row.identity_groups.model_dump().values():
            group_splits.setdefault(group, set()).add(row.intended_split)
    if any(len(splits) > 1 for splits in group_splits.values()):
        raise AssertionError("candidate identity crosses train/validation")
    if len({row.content_sha256 for row in rows}) != len(rows):
        raise AssertionError("candidate content hashes are not unique")
    _assert_content_diversity(rows)
    return DatasetCandidateManifestV2(
        dataset_id="dataset-phase6-v2-candidate",
        dataset_version="2.0",
        lifecycle_status="pending_review",
        examples=rows,
    )


def write_candidate_manifest(path: Path = OUTPUT_PATH) -> None:
    manifest = build_candidate_manifest()
    path.write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    write_candidate_manifest()
