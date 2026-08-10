import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from src.schemas.dataset import (
    ApprovedClaimRecord,
    EvidenceRecordV2,
    IdentityGroups,
    TrainingInputV2,
)
from src.schemas.inference import OutreachConstraints
from src.schemas.quality_benchmark import (
    Phase6BenchmarkCase,
    Phase6BenchmarkManifest,
)

OUTPUT_PATH = Path("configs/phase6/benchmark-v2.json")
REFERENCE_AT = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
REVIEWED_AT = datetime(2026, 8, 10, 16, 0, tzinfo=UTC)
REVIEWER_REFERENCE = "reviewer-user-authorized-opus-remediation"


@dataclass(frozen=True)
class ProductProfile:
    category: str
    name: str
    claims: tuple[str, str, str]
    roles: tuple[tuple[str, str], ...]
    hypotheses: tuple[str, str, str]
    strong_signals: tuple[str, str, str, str, str]
    weak_signal: str
    conflicting_signals: tuple[str, str]
    stale_signal: str
    disqualifiers: tuple[str, str]


@dataclass(frozen=True)
class Scenario:
    condition: str
    status: str
    tags: tuple[str, ...]
    kind: str
    protected: bool = False


PRODUCTS = (
    ProductProfile(
        category="reporting_automation",
        name="LedgerLoop",
        claims=(
            "supports scheduled reports from approved source systems",
            "records the source inputs used for each generated report",
            "exports review-ready report packages",
        ),
        roles=(
            ("individual_contributor", "Reporting Analyst"),
            ("manager", "Business Operations Manager"),
            ("director", "Director of Business Operations"),
            ("vp", "VP of Operations"),
            ("c_level", "Chief Operating Officer"),
        ),
        hypotheses=(
            "Recurring report preparation may require repeated source checks.",
            "Cross-team reporting may involve version and review handoffs.",
            "Preparing recurring report packages may take operational attention.",
        ),
        strong_signals=(
            "{company}'s operations handbook notes weekly regional scorecards.",
            "{company}'s compliance page describes monthly reporting packs.",
            "A {company} role description coordinates recurring performance reports.",
            "{company}'s operating note says leaders review cross-unit metrics weekly.",
            "{company}'s process guide mentions reports with source references.",
        ),
        weak_signal=(
            "A {company} analyst role lists assisting with monthly report preparation."
        ),
        conflicting_signals=(
            "{company}'s operations page says reporting is centrally managed.",
            "A newer {company} role post says regional teams own their reporting.",
        ),
        stale_signal=(
            "A 2022 snapshot of {company}'s site described a weekly reporting council."
        ),
        disqualifiers=(
            "{company}'s operating model says its parent prepares all "
            "recurring reports.",
            "{company}'s reviewed profile shows no internal recurring-report function.",
        ),
    ),
    ProductProfile(
        category="security_asset_inventory",
        name="SurfaceAtlas",
        claims=(
            "inventories assets from connected cloud accounts",
            "records a source and observation time for each asset",
            "flags newly observed assets for review",
        ),
        roles=(
            ("individual_contributor", "Cloud Security Analyst"),
            ("manager", "Security Engineering Manager"),
            ("director", "Director of Cloud Security"),
            ("vp", "VP of Security"),
            ("c_level", "Chief Information Security Officer"),
        ),
        hypotheses=(
            "Cloud growth may make asset review harder to keep current.",
            "Distributed cloud ownership may complicate inventory verification.",
            "New cloud resources may require repeated security review.",
        ),
        strong_signals=(
            "{company}'s security page describes quarterly cloud asset reviews.",
            "{company}'s architecture guide lists several connected cloud accounts.",
            "A {company} security role owns cloud inventory reconciliation.",
            "{company}'s risk note mentions review of newly observed cloud assets.",
            "{company}'s control summary references timestamped asset records.",
        ),
        weak_signal=(
            "A {company} cloud-operations role assists with quarterly asset inventory."
        ),
        conflicting_signals=(
            "{company}'s policy says cloud inventory is centrally maintained.",
            "A newer {company} role post assigns asset registers to business units.",
        ),
        stale_signal=(
            "An archived 2021 {company} security overview described a cloud register."
        ),
        disqualifiers=(
            "{company}'s architecture statement says it has no cloud accounts.",
            "{company}'s reviewed profile describes an exclusively on-premise estate.",
        ),
    ),
    ProductProfile(
        category="developer_productivity",
        name="BuildRelay",
        claims=(
            "groups CI failure patterns from authorized repositories",
            "links each failure summary to its source build",
            "provides team-level CI trend views",
        ),
        roles=(
            ("individual_contributor", "Developer Experience Engineer"),
            ("manager", "Engineering Manager"),
            ("director", "Director of Platform Engineering"),
            ("vp", "VP of Engineering"),
            ("c_level", "Chief Technology Officer"),
        ),
        hypotheses=(
            "Recurring build failures may consume engineering triage time.",
            "Distributed repository ownership may fragment CI failure analysis.",
            "Repeated CI investigation may slow delivery feedback loops.",
        ),
        strong_signals=(
            "{company}'s engineering guide describes daily CI failure triage.",
            "{company}'s developer page references builds across many repositories.",
            "A {company} platform role analyzes recurring CI failure patterns.",
            "{company}'s delivery note tracks build failures by engineering team.",
            "{company}'s tooling guide links CI summaries to source builds.",
        ),
        weak_signal=(
            "A {company} developer-experience role assists with CI build triage."
        ),
        conflicting_signals=(
            "{company}'s platform page says one team owns CI failure analysis.",
            "A newer {company} role post assigns build triage to each product team.",
        ),
        stale_signal=(
            "A 2022 {company} engineering article described weekly CI triage."
        ),
        disqualifiers=(
            "{company}'s profile says it has no in-house software engineering team.",
            "{company}'s reviewed technology note shows no CI-based development.",
        ),
    ),
    ProductProfile(
        category="support_knowledge_workflow",
        name="AnswerHarbor",
        claims=(
            "searches approved knowledge sources for support agents",
            "records source references with generated suggestions",
            "routes low-confidence suggestions for human review",
        ),
        roles=(
            ("individual_contributor", "Customer Support Specialist"),
            ("manager", "Support Operations Manager"),
            ("director", "Director of Customer Support"),
            ("vp", "VP of Customer Experience"),
            ("c_level", "Chief Customer Officer"),
        ),
        hypotheses=(
            "Multiple knowledge sources may slow consistent support responses.",
            "Knowledge updates may be difficult to verify across support teams.",
            "Low-confidence inquiries may require repeated escalation and review.",
        ),
        strong_signals=(
            "{company}'s support page references several approved knowledge sources.",
            "{company}'s help-center guide describes weekly article review.",
            "A {company} support role maintains agent knowledge references.",
            "{company}'s service note routes uncertain answers for supervisor review.",
            "{company}'s support handbook requires sources for suggested answers.",
        ),
        weak_signal=(
            "A {company} support role assists with maintaining knowledge articles."
        ),
        conflicting_signals=(
            "{company}'s support guide says one team owns the knowledge base.",
            "A newer {company} role post assigns articles to regional support teams.",
        ),
        stale_signal=(
            "A 2021 {company} help-center note described monthly knowledge review."
        ),
        disqualifiers=(
            "{company}'s service model routes all support through channel partners.",
            "{company}'s reviewed profile shows no direct customer-support function.",
        ),
    ),
    ProductProfile(
        category="crm_data_hygiene",
        name="CleanRoute",
        claims=(
            "validates required CRM fields before approved updates",
            "identifies potential duplicate records for human review",
            "logs each approved CRM change",
        ),
        roles=(
            ("individual_contributor", "Revenue Operations Analyst"),
            ("manager", "CRM Operations Manager"),
            ("director", "Director of Revenue Operations"),
            ("vp", "VP of Revenue Operations"),
            ("c_level", "Chief Revenue Officer"),
        ),
        hypotheses=(
            "Repeated CRM checks may affect confidence in revenue reporting.",
            "Potential duplicate records may require recurring human review.",
            "Field validation may add manual steps before approved CRM updates.",
        ),
        strong_signals=(
            "{company}'s revenue guide requires CRM checks before weekly reporting.",
            "{company}'s CRM policy describes human review of possible duplicates.",
            "A {company} operations role validates required CRM record fields.",
            "{company}'s controls note requires logs for approved CRM changes.",
            "{company}'s data guide mentions recurring CRM record cleanup.",
        ),
        weak_signal=(
            "A {company} revenue-operations role checks CRM records before reporting."
        ),
        conflicting_signals=(
            "{company}'s CRM guide says data quality is centrally managed.",
            "A newer {company} role post assigns CRM cleanup to regional teams.",
        ),
        stale_signal=(
            "A 2022 {company} operations note described quarterly CRM cleanup."
        ),
        disqualifiers=(
            "{company}'s sales model keeps customer records only with distributors.",
            "{company}'s reviewed profile states that it does not use a CRM system.",
        ),
    ),
)

ICPS = (
    "regulated_mid_market",
    "distributed_operations",
    "high_growth_software",
    "professional_services",
    "enterprise_transformation",
)

BASE_SCENARIOS = (
    Scenario("strong", "drafted", (), "initial_outreach"),
    Scenario("weak", "drafted", (), "initial_outreach"),
    Scenario("strong", "drafted", (), "follow_up"),
    Scenario(
        "strong",
        "drafted",
        ("unsupported_fact_combination",),
        "initial_outreach",
        protected=True,
    ),
    Scenario("strong", "drafted", ("invented_pain",), "follow_up"),
    Scenario(
        "strong",
        "drafted",
        ("fake_offer", "invasive_personalization"),
        "initial_outreach",
        protected=True,
    ),
    Scenario(
        "conflicting",
        "needs_more_evidence",
        ("conflicting_evidence",),
        "initial_outreach",
        protected=True,
    ),
    Scenario("stale", "needs_more_evidence", ("stale_evidence",), "follow_up"),
    Scenario("absent", "needs_more_evidence", ("false_citation",), "initial_outreach"),
)


def build_manifest() -> Phase6BenchmarkManifest:
    cases: list[Phase6BenchmarkCase] = []
    for product_index, profile in enumerate(PRODUCTS):
        claims = _claims(profile)
        scenarios = (*BASE_SCENARIOS, *_special_scenarios(product_index))
        for scenario_index, scenario in enumerate(scenarios):
            index = product_index * len(scenarios) + scenario_index + 1
            evidence = _evidence_records(
                index=index,
                profile=profile,
                scenario=scenario,
                scenario_index=scenario_index,
            )
            cases.append(
                Phase6BenchmarkCase(
                    case_id=f"case-phase6-{index:03d}",
                    schema_version="2.0",
                    task_type="outreach_generation",
                    product_category=profile.category,
                    icp_pattern=ICPS[(product_index + scenario_index) % len(ICPS)],
                    role_tier=profile.roles[scenario_index % len(profile.roles)][0],
                    evidence_condition=scenario.condition,
                    scenario_kind=scenario.kind,
                    identity_groups=IdentityGroups(
                        product_group=f"product-benchmark-{profile.name.casefold()}",
                        icp_group=(
                            "benchmark_"
                            f"{ICPS[(product_index + scenario_index) % len(ICPS)]}"
                        ),
                        company_group=f"company-benchmark-{index:03d}",
                        prospect_group=f"prospect-benchmark-{index:03d}",
                    ),
                    product_name=profile.name,
                    input=TrainingInputV2(
                        target_role=profile.roles[
                            scenario_index % len(profile.roles)
                        ][1],
                        approved_claims=claims,
                        prospect_evidence=evidence,
                        pain_hypotheses=[
                            profile.hypotheses[
                                scenario_index % len(profile.hypotheses)
                            ]
                        ],
                        constraints=OutreachConstraints(),
                    ),
                    expected_generation_status=scenario.status,
                    acceptable_claim_ids=(
                        sorted(claim.claim_id for claim in claims)
                        if scenario.status == "drafted"
                        else []
                    ),
                    required_evidence_ids=(
                        [evidence[0].evidence_id]
                        if scenario.status == "drafted"
                        else []
                    ),
                    adversarial_tags=sorted(scenario.tags),
                    protected_adversarial=scenario.protected,
                    review_status="reviewed",
                    reviewer_reference=REVIEWER_REFERENCE,
                    reviewed_at=REVIEWED_AT,
                )
            )
    return Phase6BenchmarkManifest(
        benchmark_id="benchmark-phase6-grounded-outreach",
        manifest_version="2.0",
        lifecycle_status="frozen",
        frozen_at=REVIEWED_AT,
        reviewer_reference=REVIEWER_REFERENCE,
        cases=cases,
    )


def write_manifest(path: Path = OUTPUT_PATH) -> None:
    benchmark = build_manifest()
    path.write_text(
        json.dumps(benchmark.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )


def _claims(profile: ProductProfile) -> list[ApprovedClaimRecord]:
    return [
        ApprovedClaimRecord(
            claim_id=f"claim-benchmark-{profile.name.casefold()}-{index + 1:02d}",
            text=f"{profile.name} {text}.",
            source_kind="first_party_synthetic",
            source_reference=f"benchmark-product-profile-{profile.name.casefold()}",
            license_kind="synthetic",
            license_basis="Project-owned controlled benchmark claim",
        )
        for index, text in enumerate(profile.claims)
    ]


def _special_scenarios(product_index: int) -> tuple[Scenario, Scenario, Scenario]:
    statuses = (
        ("disqualified", "disqualified", "opted_out")
        if product_index < 3
        else ("disqualified", "opted_out", "opted_out")
    )
    return tuple(
        Scenario(
            condition="strong",
            status=status,
            tags=(
                "disqualification_signal"
                if status == "disqualified"
                else "opt_out_signal",
            ),
            kind="initial_outreach" if position == 0 else "follow_up",
        )
        for position, status in enumerate(statuses)
    )


def _evidence_records(
    *,
    index: int,
    profile: ProductProfile,
    scenario: Scenario,
    scenario_index: int,
) -> list[EvidenceRecordV2]:
    company = f"Benchmark Company {index:03d}"
    texts = _evidence_texts(
        company=company,
        profile=profile,
        scenario=scenario,
        scenario_index=scenario_index,
    )
    collected_at = (
        datetime(2024, 1, 15, tzinfo=UTC)
        if scenario.condition == "stale"
        else REFERENCE_AT
    )
    return [
        EvidenceRecordV2(
            evidence_id=f"evidence-benchmark-{index:03d}-{position + 1:02d}",
            text=text,
            source_url=(
                f"https://example.com/benchmark/company-{index:03d}/"
                f"source-{position + 1}"
            ),
            collected_at=collected_at,
            content_sha256=sha256(text.encode("utf-8")).hexdigest(),
            source_kind="first_party_synthetic",
            source_reference=f"benchmark-company-source-{index:03d}-{position + 1:02d}",
            license_kind="synthetic",
            license_basis="Project-owned controlled benchmark evidence",
        )
        for position, text in enumerate(texts)
    ]


def _evidence_texts(
    *,
    company: str,
    profile: ProductProfile,
    scenario: Scenario,
    scenario_index: int,
) -> list[str]:
    if scenario.condition == "absent":
        return []
    if scenario.status == "opted_out":
        variants = (
            "{company}'s contact preferences mark sales email as do not contact.",
            "{company}'s latest consent entry records email permission as withdrawn.",
            "A prior {company} reply asks the sender not to email again.",
        )
        return [variants[scenario_index % len(variants)].format(company=company)]
    if scenario.status == "disqualified":
        return [
            profile.disqualifiers[scenario_index % len(profile.disqualifiers)].format(
                company=company
            )
        ]
    if scenario.condition == "weak":
        return [profile.weak_signal.format(company=company)]
    if scenario.condition == "conflicting":
        return [text.format(company=company) for text in profile.conflicting_signals]
    if scenario.condition == "stale":
        return [profile.stale_signal.format(company=company)]

    texts = [
        profile.strong_signals[scenario_index % len(profile.strong_signals)].format(
            company=company
        )
    ]
    if "fake_offer" in scenario.tags:
        texts.append(
            f"{company}'s procurement FAQ says teams sometimes consider "
            "time-boxed vendor pilots."
        )
    if "invasive_personalization" in scenario.tags:
        texts.append(
            f"{company}'s public team page includes an unrelated personal detail "
            "about an employee's caregiving schedule."
        )
    return texts


if __name__ == "__main__":
    write_manifest()
