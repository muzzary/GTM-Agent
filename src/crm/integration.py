from datetime import UTC, datetime
from hashlib import sha256
from urllib.parse import urlsplit

from src.crm.service import CrmService
from src.data.crm_repository import CrmRepository
from src.schemas.campaign import Campaign, CampaignState
from src.schemas.crm import (
    ActivityCreate,
    ActivityType,
    Company,
    CompanyCreate,
    ProspectCrmLinkResult,
    ProspectLinkStatus,
)


class CampaignCrmLinker:
    """Converts completed prospect evidence into a reviewable CRM company."""

    def __init__(self, service: CrmService, repository: CrmRepository) -> None:
        self._service = service
        self._repository = repository

    def link_selected_prospect(
        self,
        tenant_id: str,
        campaign: Campaign,
        idempotency_key: str,
    ) -> ProspectCrmLinkResult:
        if campaign.state is not CampaignState.PROSPECT_RESEARCHED:
            raise ValueError("selected prospect research must be completed first")
        if campaign.selected_prospect_id is None:
            raise ValueError("a selected prospect is required")
        prospect = next(
            item
            for item in campaign.prospects
            if item.prospect_id == campaign.selected_prospect_id
        )
        existing_source = next(
            (
                company
                for company in self._repository.list_companies(tenant_id)
                if company.source_campaign_id == campaign.campaign_id
                and company.source_prospect_id == prospect.prospect_id
            ),
            None,
        )
        if existing_source is not None:
            return self._linked_result(tenant_id, existing_source)

        domain = normalized_domain(prospect.official_url)
        duplicates = (
            self._repository.find_companies_by_domain(tenant_id, domain)
            if domain is not None
            else ()
        )
        if duplicates:
            return ProspectCrmLinkResult(
                status=ProspectLinkStatus.CONFLICT_REVIEW,
                duplicate_company_ids=tuple(item.company_id for item in duplicates),
                reason=(
                    "A company with the same normalized domain already exists; "
                    "review before linking."
                ),
            )

        company = self._service.create_company(
            tenant_id,
            CompanyCreate(
                company_id=f"company-{sha256(idempotency_key.encode()).hexdigest()[:24]}",
                name=prospect.company,
                normalized_domain=domain,
                website=prospect.official_url,
                industry=prospect.industry,
                region=prospect.region,
                source_prospect_id=prospect.prospect_id,
                source_campaign_id=campaign.campaign_id,
                source_evidence_ids=list(prospect.evidence_ids),
            ),
            source_evidence_ids=prospect.evidence_ids,
        )
        activity_id = sha256(
            (idempotency_key + ":research").encode()
        ).hexdigest()[:24]
        activity = self._service.create_activity(
            tenant_id,
            ActivityCreate(
                activity_id=f"activity-{activity_id}",
                entity_type="company",
                entity_id=company.company_id,
                activity_type=ActivityType.RESEARCH,
                summary=(
                    f"Completed prospect research linked from campaign "
                    f"{campaign.campaign_id}; evidence IDs: "
                    f"{', '.join(prospect.evidence_ids)}."
                ),
                occurred_at=datetime.now(UTC),
            ),
        )
        return ProspectCrmLinkResult(
            status=ProspectLinkStatus.LINKED,
            company=company,
            activity=activity,
            reason="Researched prospect linked with source evidence preserved.",
        )

    def _linked_result(self, tenant_id: str, company: Company) -> ProspectCrmLinkResult:
        activities = self._repository.list_activities(
            tenant_id, "company", company.company_id
        )
        return ProspectCrmLinkResult(
            status=ProspectLinkStatus.LINKED,
            company=company,
            activity=activities[-1] if activities else None,
            reason=(
                "The prospect is already linked; the existing CRM record was returned."
            ),
        )


def normalized_domain(url: object) -> str | None:
    if url is None:
        return None
    host = urlsplit(str(url)).hostname
    if host is None:
        return None
    host = host.casefold().rstrip(".")
    return host[4:] if host.startswith("www.") else host
