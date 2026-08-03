from collections.abc import Callable, Sequence
from datetime import datetime
from hashlib import sha256

from src.schemas.campaign import (
    ApprovalRecord,
    EvaluationCheck,
    EvaluationResult,
    EvidenceRecord,
    ICPProfile,
    OutreachDraft,
    PositioningBrief,
    ProductClaim,
    ProductProfile,
    ProspectCandidate,
    Uncertainty,
)

NewId = Callable[[str], str]


def _digest(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


class DeterministicFixturePipeline:
    """Local stage implementations that prove data flow without external claims."""

    def research_product(
        self,
        *,
        campaign_id: str,
        product: ProductProfile,
        new_id: NewId,
        collected_at: datetime,
    ) -> tuple[tuple[EvidenceRecord, ...], tuple[ProductClaim, ...]]:
        capability_text = (
            f"Submitted product details say {product.name} supports "
            f"{product.capabilities[0]}."
        )
        description_text = (
            f"Submitted product details describe {product.name} as "
            f"{product.short_description}"
        )
        excerpts = (capability_text, description_text)
        evidence = tuple(
            EvidenceRecord(
                evidence_id=new_id("evidence"),
                campaign_id=campaign_id,
                source_kind="fixture",
                title=f"Submitted details for {product.name}",
                excerpt=excerpt,
                content_sha256=_digest(excerpt),
                collected_at=collected_at,
            )
            for excerpt in excerpts
        )
        claims = (
            ProductClaim(
                claim_id=new_id("claim"),
                campaign_id=campaign_id,
                product_id=product.product_id,
                text=f"{product.name} supports {product.capabilities[0]}.",
                evidence_ids=(evidence[0].evidence_id,),
                uncertainty=Uncertainty.LOW,
            ),
            ProductClaim(
                claim_id=new_id("claim"),
                campaign_id=campaign_id,
                product_id=product.product_id,
                text=f"{product.name}: {product.short_description}",
                evidence_ids=(evidence[1].evidence_id,),
                uncertainty=Uncertainty.MEDIUM,
            ),
        )
        return evidence, claims

    def rank_prospects(
        self,
        *,
        campaign_id: str,
        icp: ICPProfile,
        new_id: NewId,
        collected_at: datetime,
    ) -> tuple[tuple[EvidenceRecord, ...], tuple[ProspectCandidate, ...]]:
        industry = icp.industries[0]
        role = icp.roles[0]
        pain = icp.pain_hypotheses[0]
        prospect_specs = (
            (f"{industry.title()} Fixture One", 0.90),
            (f"{industry.title()} Fixture Two", 0.75),
        )
        evidence_items: list[EvidenceRecord] = []
        prospects: list[ProspectCandidate] = []
        for company, score in prospect_specs:
            excerpt = (
                f"Fixture signal for {company}: {role} teams may experience {pain}."
            )
            evidence = EvidenceRecord(
                evidence_id=new_id("evidence"),
                campaign_id=campaign_id,
                source_kind="fixture",
                title=f"Synthetic ICP match for {company}",
                excerpt=excerpt,
                content_sha256=_digest(excerpt),
                collected_at=collected_at,
            )
            evidence_items.append(evidence)
            prospects.append(
                ProspectCandidate(
                    prospect_id=new_id("prospect"),
                    campaign_id=campaign_id,
                    icp_id=icp.icp_id,
                    company=company,
                    industry=industry,
                    target_role=role,
                    matched_icp_fields=("industry", "company_size", "role"),
                    public_signals=(f"Fixture pain hypothesis: {pain}",),
                    evidence_ids=(evidence.evidence_id,),
                    score=score,
                    uncertainty=Uncertainty.HIGH,
                )
            )
        return tuple(evidence_items), tuple(prospects)

    def position(
        self,
        *,
        campaign_id: str,
        product: ProductProfile,
        icp: ICPProfile,
        approved_approvals: Sequence[ApprovalRecord],
        prospect: ProspectCandidate,
        new_id: NewId,
    ) -> PositioningBrief:
        claim_evidence = tuple(
            evidence_id
            for approval in approved_approvals
            for evidence_id in approval.evidence_ids
        )
        return PositioningBrief(
            positioning_id=new_id("positioning"),
            campaign_id=campaign_id,
            prospect_id=prospect.prospect_id,
            approved_claim_ids=tuple(
                approval.claim_id for approval in approved_approvals
            ),
            approval_ids=tuple(approval.approval_id for approval in approved_approvals),
            evidence_ids=tuple(dict.fromkeys(claim_evidence + prospect.evidence_ids)),
            value_hypothesis=(
                f"Position {product.name} for {icp.roles[0]} teams at "
                f"{prospect.company} around {icp.pain_hypotheses[0]}."
            ),
        )

    def generate_draft(
        self,
        *,
        campaign_id: str,
        product: ProductProfile,
        icp: ICPProfile,
        prospect: ProspectCandidate,
        positioning: PositioningBrief,
        approved_approvals: Sequence[ApprovalRecord],
        new_id: NewId,
    ) -> OutreachDraft:
        approved_text = approved_approvals[0].reviewed_text
        return OutreachDraft(
            draft_id=new_id("draft"),
            campaign_id=campaign_id,
            prospect_id=prospect.prospect_id,
            positioning_id=positioning.positioning_id,
            subject=f"A question about {icp.pain_hypotheses[0]}",
            body=(
                f"Hi {icp.roles[0]},\n\n"
                f"Teams at {prospect.company} may be reviewing "
                f"{icp.pain_hypotheses[0]}. {approved_text} "
                f"That is why {product.name} may be relevant.\n\n"
                "Would a brief comparison be useful?"
            ),
            claim_ids=tuple(approval.claim_id for approval in approved_approvals),
            approval_ids=tuple(approval.approval_id for approval in approved_approvals),
            evidence_ids=positioning.evidence_ids,
        )

    def evaluate(
        self,
        *,
        campaign_id: str,
        draft: OutreachDraft,
        approved_approvals: Sequence[ApprovalRecord],
        evidence: Sequence[EvidenceRecord],
        selected_prospect: ProspectCandidate,
        new_id: NewId,
        evaluated_at: datetime,
    ) -> EvaluationResult:
        approved_ids = {approval.claim_id for approval in approved_approvals}
        approval_ids = {approval.approval_id for approval in approved_approvals}
        evidence_ids = {item.evidence_id for item in evidence}
        checks = (
            EvaluationCheck(
                name="schema_valid",
                passed=True,
                reason="The draft was constructed through its strict schema.",
            ),
            EvaluationCheck(
                name="approved_claims_only",
                passed=(
                    set(draft.claim_ids) <= approved_ids
                    and set(draft.approval_ids) <= approval_ids
                ),
                reason="Every referenced claim must have an approval record.",
            ),
            EvaluationCheck(
                name="evidence_resolved",
                passed=set(draft.evidence_ids) <= evidence_ids,
                reason="Every draft evidence ID must resolve in the campaign.",
            ),
            EvaluationCheck(
                name="selected_prospect",
                passed=draft.prospect_id == selected_prospect.prospect_id,
                reason="The draft must target the user-selected prospect.",
            ),
        )
        return EvaluationResult(
            evaluation_id=new_id("evaluation"),
            campaign_id=campaign_id,
            draft_id=draft.draft_id,
            passed=all(check.passed for check in checks),
            checks=list(checks),
            evaluated_at=evaluated_at,
        )
