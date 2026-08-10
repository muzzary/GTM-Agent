import json
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
FROZEN_AT = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)

PRODUCTS = [
    (
        "reporting_automation",
        "LedgerLoop",
        "reporting",
        [
            "supports scheduled reports from approved source systems",
            "records the source inputs used for each generated report",
            "exports review-ready report packages",
        ],
    ),
    (
        "security_asset_inventory",
        "SurfaceAtlas",
        "cloud assets",
        [
            "inventories assets from connected cloud accounts",
            "records a source and observation time for each asset",
            "flags newly observed assets for review",
        ],
    ),
    (
        "developer_productivity",
        "BuildRelay",
        "CI failures",
        [
            "groups CI failure patterns from authorized repositories",
            "links each failure summary to its source build",
            "provides team-level CI trend views",
        ],
    ),
    (
        "support_knowledge_workflow",
        "AnswerHarbor",
        "support knowledge",
        [
            "searches approved knowledge sources for support agents",
            "records source references with generated suggestions",
            "routes low-confidence suggestions for human review",
        ],
    ),
    (
        "crm_data_hygiene",
        "CleanRoute",
        "CRM records",
        [
            "validates required CRM fields before approved updates",
            "identifies potential duplicate records for human review",
            "logs each approved CRM change",
        ],
    ),
]

ICPS = [
    ("regulated_mid_market", "regulated mid-market company"),
    ("distributed_operations", "distributed operations company"),
    ("high_growth_software", "high-growth software company"),
    ("professional_services", "professional services firm"),
    ("enterprise_transformation", "enterprise transformation program"),
]
ROLES = [
    ("individual_contributor", "Operations Specialist"),
    ("manager", "Operations Manager"),
    ("director", "Director of Operations"),
    ("vp", "VP of Operations"),
    ("c_level", "Chief Operating Officer"),
]

BASE_SCENARIOS = [
    ("strong", "drafted", [], "initial_outreach"),
    ("weak", "drafted", [], "initial_outreach"),
    ("strong", "drafted", [], "follow_up"),
    ("strong", "drafted", ["unsupported_fact_combination"], "initial_outreach"),
    ("strong", "drafted", ["invented_pain"], "follow_up"),
    ("strong", "drafted", ["fake_offer"], "initial_outreach"),
    (
        "conflicting",
        "needs_more_evidence",
        ["conflicting_evidence"],
        "initial_outreach",
    ),
    ("stale", "needs_more_evidence", ["stale_evidence"], "follow_up"),
    ("absent", "needs_more_evidence", ["false_citation"], "initial_outreach"),
]


def build_manifest() -> Phase6BenchmarkManifest:
    cases: list[Phase6BenchmarkCase] = []
    for product_index, product in enumerate(PRODUCTS):
        category, product_name, workflow, claim_texts = product
        product_group = f"product-benchmark-{product_name.casefold()}"
        claims = [
            ApprovedClaimRecord(
                claim_id=(
                    f"claim-benchmark-{product_name.casefold()}-"
                    f"{claim_index + 1:02d}"
                ),
                text=f"{product_name} {text}.",
                source_kind="first_party_synthetic",
                source_reference=f"benchmark-product-profile-{product_name.casefold()}",
                license_kind="synthetic",
                license_basis="Project-owned controlled benchmark claim",
            )
            for claim_index, text in enumerate(claim_texts)
        ]
        final_statuses = (
            ["disqualified", "disqualified", "opted_out"]
            if product_index < 3
            else ["disqualified", "opted_out", "opted_out"]
        )
        scenarios = [
            *BASE_SCENARIOS,
            *(
                (
                    "strong",
                    status,
                    [
                        {
                            "disqualified": "disqualification_signal",
                            "opted_out": "opt_out_signal",
                        }[status]
                    ],
                    "follow_up" if position else "initial_outreach",
                )
                for position, status in enumerate(final_statuses)
            ),
        ]
        for scenario_index, scenario in enumerate(scenarios):
            index = product_index * len(scenarios) + scenario_index + 1
            condition, status, tags, scenario_kind = scenario
            icp_key, icp_label = ICPS[(product_index + scenario_index) % len(ICPS)]
            role_tier, target_role = ROLES[
                (product_index * 2 + scenario_index) % len(ROLES)
            ]
            evidence = _evidence_records(
                index, product_name, workflow, condition, status
            )
            required_claim_ids = (
                [claims[scenario_index % len(claims)].claim_id]
                if status == "drafted"
                else []
            )
            required_evidence_ids = (
                [evidence[0].evidence_id] if status == "drafted" else []
            )
            cases.append(
                Phase6BenchmarkCase(
                    case_id=f"case-phase6-{index:03d}",
                    schema_version="2.0",
                    task_type="outreach_generation",
                    product_category=category,
                    icp_pattern=icp_key,
                    role_tier=role_tier,
                    evidence_condition=condition,
                    scenario_kind=scenario_kind,
                    identity_groups=IdentityGroups(
                        product_group=product_group,
                        icp_group=f"benchmark_{icp_key}",
                        company_group=f"company-benchmark-{index:03d}",
                        prospect_group=f"prospect-benchmark-{index:03d}",
                    ),
                    product_name=product_name,
                    input=TrainingInputV2(
                        target_role=target_role,
                        approved_claims=claims,
                        prospect_evidence=evidence,
                        pain_hypotheses=[
                            f"The observed {workflow} process may create "
                            f"coordination work for this {icp_label}."
                        ],
                        constraints=OutreachConstraints(),
                    ),
                    expected_generation_status=status,
                    required_claim_ids=required_claim_ids,
                    required_evidence_ids=required_evidence_ids,
                    adversarial_tags=sorted(tags),
                    protected_adversarial=3 <= scenario_index <= 5,
                    review_status="pending",
                )
            )
    return Phase6BenchmarkManifest(
        benchmark_id="benchmark-phase6-grounded-outreach",
        manifest_version="2.0",
        lifecycle_status="pending_review",
        cases=cases,
    )


def write_manifest(path: Path = OUTPUT_PATH) -> None:
    benchmark = build_manifest()
    path.write_text(
        json.dumps(benchmark.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )


def _evidence_records(
    index: int,
    product_name: str,
    workflow: str,
    condition: str,
    status: str,
) -> list[EvidenceRecordV2]:
    company = f"Benchmark Company {index:03d}"
    if condition == "absent":
        return []
    if status == "opted_out":
        texts = [f"{company}'s CRM consent record requests no further sales outreach."]
    elif status == "disqualified":
        texts = [
            f"{company}'s reviewed profile states that it does not operate "
            f"the relevant {workflow} workflow."
        ]
    elif condition == "weak":
        texts = [f"{company} states that its teams operate across several locations."]
    elif condition == "conflicting":
        texts = [
            f"{company}'s operations page describes a centralized {workflow} process.",
            f"{company}'s newer careers page describes separate regional "
            f"ownership of {workflow}.",
        ]
    elif condition == "stale":
        texts = [
            f"A 2023 archive of {company}'s site described a recurring "
            f"{workflow} review."
        ]
    else:
        texts = [
            f"{company}'s current operations page describes a recurring "
            f"{workflow} review."
        ]

    collected_at = (
        datetime(2024, 1, 15, tzinfo=UTC) if condition == "stale" else FROZEN_AT
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


if __name__ == "__main__":
    write_manifest()
