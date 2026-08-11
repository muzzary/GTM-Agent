"""Build the deterministic, pending-review Phase 6 v2 candidate dataset."""

# Hand-authored sentence pools are kept readable as prose; other lint rules remain active.
# ruff: noqa: E501

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
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
REFERENCE_DATE = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
COLLECTED_AT = REFERENCE_DATE

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
            "offers an exportable report package for a supervised pilot",
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
            "offers a bounded asset review workspace for a supervised pilot",
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
            "offers a repository-level triage workspace for a supervised pilot",
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
            "offers a source-review queue for a supervised pilot",
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
            "offers a controlled duplicate-review workspace for a supervised pilot",
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

BOUND_RATIONALES = {
    "absent": (
        "No usable prospect evidence was found, so a grounded message would be speculative.",
        "This row has no usable evidence for a responsible outreach decision.",
        "No evidence supports a specific observation about this prospect.",
        "A grounded message is not possible because usable evidence is absent.",
        "There is no usable prospect evidence to support personalization here.",
        "Without usable evidence, this outreach decision should remain on hold.",
        "No prospect evidence is available for a defensible outreach message.",
        "This row lacks usable evidence for a fact-based introduction.",
        "A responsible draft cannot be grounded because no usable evidence was found.",
        "The input contains no usable prospect evidence for this workflow.",
        "No usable evidence connects this prospect to a specific outreach observation.",
        "This message should remain empty because the prospect has no usable evidence.",
    ),
    "stale": (
        "The available evidence is more than twelve months old, so the current workflow is uncertain.",
        "Evidence older than twelve months cannot establish the prospect's present priority.",
        "The evidence has aged beyond twelve months and needs current confirmation.",
        "A message should wait because the available evidence is more than twelve months old.",
        "The current situation is unclear because every available item is at least twelve months old.",
        "Evidence age exceeds twelve months, which makes a current personalization claim unsafe.",
        "The prospect signal needs refreshing because the evidence is more than twelve months old.",
        "A current source is needed because the available evidence is at least twelve months old.",
        "The evidence is too old to support a confident message about the present workflow.",
        "More recent evidence is required because the available material is beyond twelve months old.",
        "The row remains unresolved while its evidence is more than twelve months out of date.",
        "The evidence age prevents a reliable current observation for outreach.",
    ),
    "conflicting": (
        "Two sources disagree about team ownership, so a human should reconcile them first.",
        "The evidence describes different owners for the workflow and needs reconciliation.",
        "Conflicting evidence prevents a reliable statement about who runs this process.",
        "The sources point to different responsibilities, so the current owner is uncertain.",
        "A human should resolve the disagreement between the available workflow descriptions.",
        "The evidence does not agree on ownership and cannot yet support personalization.",
        "Different source descriptions leave the responsible team unresolved.",
        "The ownership conflict needs review before an outreach observation is drafted.",
        "The available sources disagree about the workflow boundary.",
        "A grounded message should wait until the conflicting responsibilities are reconciled.",
        "The evidence gives incompatible descriptions of who owns this work.",
        "The row needs review because its sources do not describe one consistent owner.",
    ),
    "weak": (
        "The available evidence is thin and indirect, so it does not support a confident message.",
        "Only an indirect role signal is available, which is not enough for personalization.",
        "The evidence is a light operational hint rather than a confirmed current priority.",
        "A single indirect reference does not establish who owns this workflow.",
        "The prospect signal is too thin to support a specific observation.",
        "The available detail suggests involvement but does not confirm an active need.",
        "A weak role signal needs corroboration before it can ground outreach.",
        "The evidence is limited to indirect assistance language and needs confirmation.",
        "The current input is suggestive but too thin for a responsible draft.",
        "An indirect mention is not enough to establish a current workflow problem.",
        "The available evidence hints at involvement without proving ownership or urgency.",
        "More direct evidence is needed because the present signal is too limited.",
    ),
}


PRODUCT_CLAIM_FORMS = (
    "{product} {claim}.",
    "{product} also {claim}.",
    "{product} directly {claim}.",
    "{product} reliably {claim}.",
    "{product} consistently {claim}.",
    "{product} currently {claim}.",
    "{product} {claim} for review.",
    "{product} {claim} across the workflow.",
    "{product} {claim} with clear ownership.",
    "{product} {claim} in a controlled process.",
    "{product} {claim} beside existing operations.",
    "{product} {claim} for the operating team.",
    "{product} {claim} before the next handoff.",
    "{product} {claim} with a traceable record.",
    "{product} {claim} during routine review.",
    "{product} {claim} as part of the team workflow.",
    "{product} {claim} without changing source ownership.",
    "{product} {claim} when the process needs consistency.",
    "{product} {claim} across the relevant team.",
    "{product} {claim} while keeping review decisions visible.",
    "{product} {claim} where the workflow needs evidence.",
    "{product} {claim} with less manual follow-up.",
    "{product} {claim} in the approved operating context.",
    "{product} {claim} for a focused review.",
    "{product} {claim} at the point of decision.",
    "{product} {claim} as a repeatable team step.",
    "{product} {claim} with the relevant context attached.",
    "{product} {claim} across recurring work.",
    "{product} {claim} when ownership is distributed.",
    "{product} {claim} in a source-aware workflow.",
    "{product} {claim} for the next operating cycle.",
    "{product} {claim} with a clear review path.",
    "{product} {claim} as teams coordinate the work.",
    "{product} {claim} in day-to-day operations.",
    "{product} {claim} when teams need a current view.",
    "{product} {claim} with the approved process.",
    "{product} {claim} before teams act on the result.",
    "{product} {claim} with the surrounding workflow intact.",
    "{product} {claim} for teams sharing responsibility.",
    "{product} {claim} when the review cycle repeats.",
    "{product} {claim} with the relevant decision in view.",
    "{product} {claim} across the team handoff.",
    "{product} {claim} when source context matters.",
    "{product} {claim} as part of a repeatable review.",
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


EVIDENCE_TEXTS = {
    "reporting_automation": {
        "strong": (
            "The careers page lists a Reporting Operations Analyst responsible for weekly compliance packs.",
            "The operations guide says regional leaders reconcile source references before monthly reviews.",
            "The annual report describes recurring scorecards prepared for cross-functional leadership meetings.",
            "The finance page describes a monthly close pack reviewed by regional operations leaders.",
            "The operations careers page assigns source reconciliation to a reporting coordinator.",
            "The compliance guide calls for weekly metrics to be checked before executive review.",
            "The leadership update refers to recurring performance packs shared across departments.",
            "The process page describes a handoff from analysts to leaders before scorecard sign-off.",
        ),
        "weak": (
            "A public role brief mentions assisting with periodic reporting updates for the operations team.",
            "The hiring page briefly references support for monthly report preparation.",
        ),
    },
    "security_asset_inventory": {
        "strong": (
            "The security architecture page lists quarterly reviews of assets across connected cloud accounts.",
            "The cloud operations guide names an owner for reconciling newly observed resources.",
            "The risk report describes timestamped asset records used during security attestations.",
            "The cloud governance page describes an inventory check before quarterly access reviews.",
            "The security careers page assigns ownership for reconciling assets across accounts.",
            "The control guide calls for newly observed resources to be reviewed by security staff.",
            "The architecture update refers to a growing register of connected cloud resources.",
            "The audit page describes source and observation time checks for cloud assets.",
        ),
        "weak": (
            "A public cloud security role mentions assisting with periodic asset inventory checks.",
            "The hiring page briefly references support for cloud account review.",
        ),
    },
    "developer_productivity": {
        "strong": (
            "The engineering handbook describes daily CI failure triage across several repositories.",
            "The platform guide links recurring build failures to their owning engineering teams.",
            "The delivery report tracks failure patterns by repository and release group.",
            "The engineering careers page assigns build health review to a platform team.",
            "The release guide calls for recurring failures to be discussed after each deployment.",
            "The developer portal describes repository-level checks before release sign-off.",
            "The platform update refers to build trends reviewed across product teams.",
            "The engineering process page links release readiness to recent build health.",
        ),
        "weak": (
            "A public developer productivity role mentions assisting with periodic build triage.",
            "The hiring page briefly references support for CI build review.",
        ),
    },
    "support_knowledge_workflow": {
        "strong": (
            "The help-center guide lists several approved knowledge sources for support agents.",
            "The support handbook requires source references when agents suggest an answer.",
            "The service note routes uncertain customer answers to supervisor review.",
            "The support careers page assigns article quality checks to an enablement team.",
            "The help-center process calls for source review before agents publish a response.",
            "The customer service guide describes a queue for questions without a clear answer.",
            "The support update refers to article ownership across several service groups.",
            "The knowledge page describes weekly checks for current guidance and source links.",
        ),
        "weak": (
            "A public support role mentions assisting with periodic knowledge article review.",
            "The hiring page briefly references support for maintaining help-center content.",
        ),
    },
    "crm_data_hygiene": {
        "strong": (
            "The revenue operations guide requires CRM checks before weekly pipeline reporting.",
            "The data policy assigns human review to possible duplicate customer records.",
            "The controls page requires an audit trail for approved CRM record changes.",
            "The sales operations page assigns duplicate review to a revenue systems team.",
            "The CRM guide calls for field checks before records enter the forecast process.",
            "The data governance update describes exception review for incomplete customer records.",
            "The revenue careers page assigns record-quality checks before pipeline reporting.",
            "The operations policy refers to approved changes being logged for later review.",
        ),
        "weak": (
            "A public revenue systems role mentions assisting with periodic CRM record checks.",
            "The hiring page briefly references support for customer data cleanup.",
        ),
    },
}

OBSERVATION_TEXTS = {
    "reporting_automation": {
        "strong": (
            "Regional leaders at {company} reconcile source references before each monthly review.",
            "{company} prepares recurring scorecards for cross-functional leadership meetings.",
            "Weekly compliance packs at {company} move through a defined review handoff.",
            "Finance leaders at {company} review source-backed metrics before the monthly close.",
            "{company} shares recurring performance packs with several operating teams.",
            "Analysts at {company} reconcile reporting inputs before leadership sign-off.",
            "The reporting calendar at {company} includes recurring regional scorecards.",
            "{company} coordinates a handoff from reporting analysts to operations leaders.",
        ),
        "weak": (
            "The reporting team at {company} appears to assist with periodic updates.",
            "Monthly report preparation seems to involve an operations role at {company}.",
        ),
    },
    "security_asset_inventory": {
        "strong": (
            "Security teams at {company} review assets across connected cloud accounts each quarter.",
            "{company} assigns ownership for reconciling newly observed resources.",
            "Security attestations at {company} use timestamped asset records.",
            "Cloud owners at {company} review new resources between scheduled attestations.",
            "{company} tracks connected account changes during security operations reviews.",
            "Security leaders at {company} reconcile asset ownership across cloud teams.",
            "The cloud estate at {company} changes often enough to require recurring checks.",
            "{company} keeps an operating view of assets that appear between reviews.",
        ),
        "weak": (
            "A security role at {company} appears to assist with periodic asset checks.",
            "Cloud account review seems to involve an operations role at {company}.",
        ),
    },
    "developer_productivity": {
        "strong": (
            "Engineering teams at {company} triage CI failures across several repositories each day.",
            "{company} connects recurring build failures with their owning engineering teams.",
            "Release groups at {company} track failure patterns by repository.",
            "Platform engineers at {company} review build health after each deployment.",
            "{company} compares CI trends across product repositories and release groups.",
            "Engineering leaders at {company} monitor recurring failures during delivery reviews.",
            "The repository estate at {company} creates a regular need for build triage.",
            "{company} connects release readiness with current delivery feedback.",
        ),
        "weak": (
            "A developer productivity role at {company} appears to assist with periodic build triage.",
            "CI build review seems to involve an engineering role at {company}.",
        ),
    },
    "support_knowledge_workflow": {
        "strong": (
            "Support agents at {company} work across several approved knowledge sources.",
            "Agents at {company} attach source references when suggesting an answer.",
            "Uncertain customer answers at {company} move to supervisor review.",
            "Support leaders at {company} check knowledge sources before changing guidance.",
            "{company} coordinates article ownership across several customer service groups.",
            "Agents at {company} escalate questions when the current answer is unclear.",
            "The support queue at {company} includes questions that need source checking.",
            "{company} keeps customer guidance aligned across a distributed support team.",
        ),
        "weak": (
            "A support role at {company} appears to assist with periodic article review.",
            "Help-center maintenance seems to involve an enablement role at {company}.",
        ),
    },
    "crm_data_hygiene": {
        "strong": (
            "Revenue operations at {company} checks CRM records before weekly pipeline reporting.",
            "{company} assigns possible duplicate customer records to human review.",
            "Approved CRM changes at {company} retain an audit trail.",
            "Revenue leaders at {company} review record exceptions before forecast updates.",
            "{company} checks field completeness as customer records enter pipeline reporting.",
            "Operations staff at {company} reconcile record quality before weekly reviews.",
            "The sales process at {company} creates recurring work around duplicate records.",
            "{company} keeps review decisions attached to approved data changes.",
        ),
        "weak": (
            "A revenue systems role at {company} appears to assist with periodic CRM checks.",
            "Customer data cleanup seems to involve an operations role at {company}.",
        ),
    },
}


def _evidence(
    index: int,
    condition: str,
    company: str,
    status: str,
    category: str,
) -> list[EvidenceRecordV2]:
    if status == "disqualified":
        texts = (
            f"{company}'s parent organization prepares all recurring reports for this business.",
            f"{company}'s reviewed profile states that it has no internal CRM system.",
            f"{company}'s operating model routes customer support through channel partners.",
            f"{company}'s architecture note describes an exclusively on-premise estate.",
            f"{company}'s profile shows no in-house software engineering team.",
            f"{company}'s customer records remain with distributors rather than this sales team.",
            f"{company}'s operating model assigns all reporting decisions to an external parent team.",
            f"{company}'s service model leaves no internal owner for the proposed workflow.",
        )
        selected_texts = [texts[index % len(texts)]]
    elif status == "opted_out":
        texts = (
            f"A prior reply from {company} asks the sender not to email again.",
            f"{company}'s contact preference record marks sales email as do not contact.",
            f"{company}'s latest consent entry records email permission as withdrawn.",
            f"{company}'s preference center lists this contact as opted out of sales outreach.",
            f"A previous message from {company} requests no further contact from vendors.",
            f"{company}'s communication record blocks promotional email to this prospect.",
            f"The consent history for {company} records a direct request to stop sales messages.",
            f"{company}'s contact record rejects further vendor outreach by email.",
        )
        selected_texts = [texts[index % len(texts)]]
    elif condition == "absent":
        selected_texts = []
    else:
        texts = {
            "strong": EVIDENCE_TEXTS[category]["strong"],
            "weak": EVIDENCE_TEXTS[category]["weak"],
            "conflicting": (
                f"{company}'s policy assigns process ownership centrally, while a newer role assigns it to regional teams.",
                f"{company}'s operating guide names one owner, but a later team brief gives regional groups responsibility.",
            ),
            "stale": (
                f"An archived {company} process note describes recurring review activity from an earlier operating period.",
                f"A prior operating record from {company} documented recurring review activity during an earlier period.",
            ),
        }[condition]
        evidence_count = 3 if condition == "strong" else 2
        selected_texts = [
            texts[(index + offset) % len(texts)] for offset in range(evidence_count)
        ]
        if condition in {"strong", "weak"}:
            selected_texts = [
                f"Public evidence from {company}: {text}"
                for text in selected_texts
            ]
    if not selected_texts:
        return []
    return [
        EvidenceRecordV2(
            evidence_id=f"evidence-candidate-{index:03d}-{position + 1:02d}",
            text=text,
            source_url=f"https://example.com/candidate/source-{index:03d}-{position + 1:02d}",
            collected_at=REFERENCE_DATE - timedelta(days=420)
            if condition == "stale"
            else COLLECTED_AT,
            content_sha256=sha256(text.encode("utf-8")).hexdigest(),
            source_kind="first_party_synthetic",
            source_reference=f"candidate-company-source-{index:03d}-{position + 1:02d}",
            license_kind=LicenseKind.SYNTHETIC,
            license_basis="Project-owned controlled candidate dataset evidence",
        )
        for position, text in enumerate(selected_texts)
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


def _draft_clean(
    profile: ProductProfile,
    claims: list[ApprovedClaimRecord],
    evidence: list[EvidenceRecordV2],
    row_index: int,
    company: str,
    condition: str,
) -> GroundedOutreachOutput:
    claim_ids = sorted(claim.claim_id for claim in claims)
    patterns = (
        ("fact", "fact", "product", "cta"),
        ("fact", "fact", "hypothesis", "product", "cta"),
        ("fact", "hypothesis", "fact", "product", "cta"),
        ("fact", "fact", "product", "hypothesis", "cta"),
        ("fact", "hypothesis", "product", "fact", "cta"),
        ("fact", "fact", "product", "product", "cta"),
        ("fact", "hypothesis", "fact", "product", "hypothesis", "cta"),
        ("fact", "product", "fact", "hypothesis", "cta"),
    )
    entries: list[SupportMapEntry] = []
    fact_position = 0
    product_position = 0
    for position, role in enumerate(patterns[row_index % len(patterns)]):
        if role == "fact":
            if fact_position >= len(evidence):
                continue
            item = evidence[fact_position]
            observation = OBSERVATION_TEXTS[profile.category][condition][
                (row_index + fact_position)
                % len(OBSERVATION_TEXTS[profile.category][condition])
            ].format(company=company)
            entries.append(
                SupportMapEntry(
                    sentence=observation,
                    role="prospect_fact",
                    evidence_ids=[item.evidence_id],
                )
            )
            fact_position += 1
        elif role == "product":
            claim_position = product_position % 2
            sentence = PRODUCT_CLAIM_FORMS[
                (row_index + position) % len(PRODUCT_CLAIM_FORMS)
            ].format(product=profile.name, claim=profile.claims[claim_position])
            entries.append(
                SupportMapEntry(
                    sentence=sentence,
                    role="product_claim",
                    claim_ids=[claim_ids[claim_position]],
                )
            )
            product_position += 1
        elif role == "hypothesis":
            entries.append(
                SupportMapEntry(
                    sentence=profile.hypotheses[
                        (row_index + position) % len(profile.hypotheses)
                    ],
                    role="hypothesis",
                )
            )
        else:
            cta_sentence, cta_kind = CTA_FORMS[row_index % len(CTA_FORMS)]
            cta_claim = claim_ids[2] if cta_kind == "approved_offer" else claim_ids[1]
            entries.append(
                SupportMapEntry(
                    sentence=cta_sentence,
                    role="cta",
                    claim_ids=[cta_claim],
                    cta_kind=cta_kind,
                )
            )
    if not 3 <= len(entries) <= 6:
        raise AssertionError("clean draft must contain three to six support entries")
    return GroundedOutreachOutput(
        generation_status="drafted",
        subject=SUBJECT_FORMS[row_index % len(SUBJECT_FORMS)].format(company=company),
        body=" ".join(entry.sentence for entry in entries),
        support_map=entries,
    )


NOTE_PREFIXES = (
    "Hold outreach: ",
    "Do not draft yet — ",
    "Review gate: ",
    "Evidence gate: ",
    "Outreach blocked because ",
    "Not ready for copy: ",
    "Decision to abstain: ",
    "Pause this row: ",
)


def _output(
    profile: ProductProfile,
    claims: list[ApprovedClaimRecord],
    evidence: list[EvidenceRecordV2],
    status: str,
    index: int,
    company: str,
    condition: str,
) -> GroundedOutreachOutput:
    if status == "drafted":
        return _draft_clean(profile, claims, evidence, index, company, condition)
    if status == "needs_more_evidence":
        if condition == "strong":
            raise AssertionError("needs_more_evidence cannot use strong evidence")
        rationale = BOUND_RATIONALES[condition][
            index % len(BOUND_RATIONALES[condition])
        ]
    elif status == "disqualified":
        fact = evidence[0].text
        clause = fact.rstrip(".")
        if not any(clause.startswith(company) for company in COMPANIES):
            clause = clause[0].lower() + clause[1:]
        rationale = "The disqualifying fact is that " + clause + "."
    else:
        fact = evidence[0].text
        clause = fact.rstrip(".")
        if not any(clause.startswith(company) for company in COMPANIES):
            clause = clause[0].lower() + clause[1:]
        rationale = "The opt-out record states that " + clause + "."
    return GroundedOutreachOutput(
        generation_status=status,
        subject="",
        body="",
        uncertainty_notes=[rationale],
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


def _row_condition(row: TrainingExampleCandidateV2) -> str:
    evidence = row.input.prospect_evidence
    if not evidence:
        return "absent"
    if any(
        REFERENCE_DATE - item.collected_at >= timedelta(days=365)
        for item in evidence
    ):
        return "stale"
    combined = " ".join(item.text.casefold() for item in evidence)
    if any(
        marker in combined
        for marker in ("while", "but a later", "disagree", "different")
    ):
        return "conflicting"
    if any(
        marker in combined
        for marker in ("assisting", "assist", "briefly references support")
    ):
        return "weak"
    return "strong"


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
        condition = _row_condition(row)
        status = row.proposed_output.generation_status
        notes = " ".join(row.proposed_output.uncertainty_notes).casefold()
        if status == "needs_more_evidence" and condition == "strong":
            raise AssertionError("needs_more_evidence cannot use strong evidence")
        if status != "drafted" and condition == "absent":
            if row.input.prospect_evidence:
                raise AssertionError("absent condition has evidence")
            if not any(
                phrase in notes
                for phrase in (
                    "no usable prospect evidence",
                    "no usable evidence",
                    "no evidence",
                    "without usable evidence",
                    "lacks usable evidence",
                    "no prospect evidence",
                    "evidence is absent",
                )
            ):
                raise AssertionError("absent rationale is not in the no-evidence family")
            if any(
                marker in notes
                for marker in (
                    "source",
                    "signal",
                    "role",
                    "month",
                    "year",
                    "old",
                    "ownership",
                    "disagree",
                )
            ):
                raise AssertionError("absent rationale names an unavailable signal")
        elif status != "drafted" and condition == "stale":
            if not row.input.prospect_evidence or any(
                REFERENCE_DATE - item.collected_at < timedelta(days=365)
                for item in row.input.prospect_evidence
            ):
                raise AssertionError("stale evidence is less than twelve months old")
            if not any(marker in notes for marker in ("old", "age", "earlier", "year", "recent", "date")):
                raise AssertionError(
                    f"stale rationale does not cite recency: {row.example_id} {notes}"
                )
        elif status != "drafted" and condition == "conflicting":
            if len(row.input.prospect_evidence) < 2:
                raise AssertionError("conflicting condition needs multiple evidence items")
            if not any(
                marker in notes
                for marker in ("disagree", "conflict", "different", "incompatible", "responsib", "agree")
            ):
                raise AssertionError("conflicting rationale does not cite disagreement")
        elif status != "drafted" and condition == "weak":
            if not row.input.prospect_evidence or not any(
                marker in notes
                for marker in ("thin", "indirect", "limited", "hint", "assist", "suggest", "weak")
            ):
                raise AssertionError(
                    f"weak rationale does not cite thin evidence: {row.example_id} {notes}"
                )
            if any(marker in notes for marker in ("old", "year", "disagree", "conflict")):
                raise AssertionError("weak rationale cites another evidence condition")
        if status in {"disqualified", "opted_out"}:
            evidence_words = set(
                re.findall(
                    r"[a-z]{5,}",
                    " ".join(item.text.casefold() for item in row.input.prospect_evidence),
                )
            )
            note_words = set(re.findall(r"[a-z]{5,}", notes))
            if not evidence_words & note_words:
                raise AssertionError("abstention rationale is not grounded in evidence")
        duration = re.search(
            r"\b(one|two|three|four|five|six|seven|eight|nine|ten|twelve|fourteen|\d+)\s+months?\b",
            notes,
        )
        if duration:
            month_words = {
                "one": 1,
                "two": 2,
                "three": 3,
                "four": 4,
                "five": 5,
                "six": 6,
                "seven": 7,
                "eight": 8,
                "nine": 9,
                "ten": 10,
                "twelve": 12,
                "fourteen": 14,
            }
            months = month_words.get(duration.group(1))
            if months is None:
                months = int(duration.group(1))
            if condition != "stale" or any(
                REFERENCE_DATE - item.collected_at < timedelta(days=months * 30)
                for item in row.input.prospect_evidence
            ):
                raise AssertionError("rationale states an inaccurate evidence duration")
        evidence_by_id = {
            item.evidence_id: item.text for item in row.input.prospect_evidence
        }
        evidence_references = [
            evidence_id
            for entry in row.proposed_output.support_map
            for evidence_id in entry.evidence_ids
        ]
        claim_references = [
            claim_id
            for entry in row.proposed_output.support_map
            for claim_id in entry.claim_ids
        ]
        if len(evidence_references) != len(set(evidence_references)):
            raise AssertionError("an evidence ID is cited by multiple support entries")
        if any(claim_references.count(claim_id) > 2 for claim_id in set(claim_references)):
            raise AssertionError("a claim ID is cited by more than two support entries")
        if any(not re.search(r"[.!?]$", item.text) for item in row.input.prospect_evidence):
            raise AssertionError("evidence text must be a complete sentence")
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
    if re.search(r"\b(Crm|Ci)\b", output_text):
        raise AssertionError("acronym capitalization is not canonical")
    banned_support_phrases = (
        "public evidence",
        "public record",
        "the source",
        "according to",
        "the approved product profile",
        "operating guide",
        "careers page",
        "hiring page",
        "annual report",
        "job post",
        "public materials",
        "team page",
        "operations page",
        "process note",
        "role brief",
        "role details",
        "published workflow",
    )
    for output in outputs:
        for entry in output.support_map:
            lowered = entry.sentence.casefold()
            if any(phrase in lowered for phrase in banned_support_phrases):
                raise AssertionError("support sentence contains a sourcing label")
            if ":" in entry.sentence:
                raise AssertionError("support sentence contains a colon")
        for note in output.uncertainty_notes:
            if re.match(r"^\s*[A-Za-z][A-Za-z -]*:", note):
                raise AssertionError("abstention note has a label prefix")
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
            f"distinct={len(rationale_counts)}, max_reuse={max(rationale_counts.values(), default=0)}, "
            f"examples={rationale_counts.most_common(5)}"
        )
    shapes = Counter(
        tuple(entry.role for entry in output.support_map) for output in drafted
    )
    if len(shapes) < 6 or max(shapes.values(), default=0) > len(drafted) * 0.4:
        raise AssertionError("support-map role-shape diversity threshold failed")
    body_counts = [len(re.findall(r"\b[\w'-]+\b", output.body)) for output in drafted]
    if any(not 40 <= count <= 95 for count in body_counts):
        raise AssertionError(
            "draft body length must be between 40 and 95 words: "
            f"min={min(body_counts, default=0)}, max={max(body_counts, default=0)}"
        )
    if any(not 3 <= len(output.support_map) <= 6 for output in drafted):
        raise AssertionError("draft support maps must contain three to six entries")
    for output in drafted:
        if not 1 <= sum(entry.role == "prospect_fact" for entry in output.support_map) <= 3:
            raise AssertionError("drafts must contain one to three prospect facts")
    frame_counts: Counter[str] = Counter()
    for row in rows:
        claims_by_id = {claim.claim_id: claim.text for claim in row.input.approved_claims}
        for entry in row.proposed_output.support_map:
            if entry.role == "product_claim":
                claim_text = claims_by_id[entry.claim_ids[0]].rstrip(".")
                frame = entry.sentence.replace(claim_text, "<claim>")
                frame_counts[frame] += 1
    if max(frame_counts.values(), default=0) > 3:
        raise AssertionError(
            "a product-claim frame is reused more than three times: "
            f"max={max(frame_counts.values(), default=0)}, "
            f"examples={frame_counts.most_common(3)}"
        )
    company_prefixed_notes = sum(
        any(note.startswith(f"{company}:") for company in COMPANIES)
        for output in abstentions
        for note in output.uncertainty_notes
    )
    if company_prefixed_notes > len(abstentions) * 0.3:
        raise AssertionError("too many abstention notes begin with a company name")
    company_names = {
        name
        for row in rows
        for name in COMPANIES
        if name in json.dumps(row.model_dump(mode="json"))
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
    evidence = _evidence(evidence_index, condition, company, status, profile.category)
    inputs = TrainingInputV2(
        target_role=profile.roles[identity_index % len(profile.roles)][1],
        approved_claims=claims,
        prospect_evidence=evidence,
        pain_hypotheses=[profile.hypotheses[index % len(profile.hypotheses)]],
        constraints=OutreachConstraints(),
    )
    output = _output(profile, claims, evidence, status, index, company, condition)
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
                if status == "needs_more_evidence":
                    condition = ("weak", "conflicting", "stale", "absent")[index % 4]
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
