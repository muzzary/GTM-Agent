from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from hashlib import sha256

from pydantic import Field, HttpUrl

from src.crm.service import CrmService
from src.schemas.base import StrictModel
from src.schemas.crm import CompanyCreate, DealCreate


class SearchCompaniesArguments(StrictModel):
    query: str = Field(min_length=1, max_length=120)


class CreateCompanyArguments(StrictModel):
    idempotency_key: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=160)
    normalized_domain: str | None = Field(default=None, max_length=255)
    website: HttpUrl | None = None
    industry: str | None = Field(default=None, max_length=120)
    region: str | None = Field(default=None, max_length=120)


class CreateDealArguments(StrictModel):
    company_id: str = Field(pattern=r"^company-[a-z0-9-]{4,64}$")
    contact_id: str | None = Field(default=None, pattern=r"^contact-[a-z0-9-]{4,64}$")
    pipeline_id: str = Field(pattern=r"^pipeline-[a-z0-9-]{4,64}$")
    stage_id: str = Field(pattern=r"^stage-[a-z0-9-]{4,64}$")
    name: str = Field(min_length=1, max_length=160)
    amount_minor: int = Field(ge=0, le=10**15)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    idempotency_key: str = Field(min_length=1, max_length=128)


class InspectSelectedProspectArguments(StrictModel):
    campaign_id: str = Field(pattern=r"^campaign-[a-z0-9-]{4,64}$")


class LinkSelectedProspectArguments(StrictModel):
    campaign_id: str = Field(pattern=r"^campaign-[a-z0-9-]{4,64}$")
    idempotency_key: str = Field(min_length=1, max_length=128)


class RevenueReportArguments(StrictModel):
    as_of: date = Field(strict=False)
    currency: str = Field(pattern=r"^[A-Z]{3}$")


@dataclass(frozen=True)
class ToolSpec:
    name: str
    version: str
    argument_model: type[StrictModel]
    requires_approval: bool
    handler: Callable[[str, StrictModel], dict[str, object]]


class CrmToolRegistry:
    """Allowlisted CRM tools; model output never receives the repository."""

    def __init__(
        self,
        service: CrmService,
        prospect_reader: Callable[[str, str], dict[str, object]] | None = None,
        prospect_linker: Callable[[str, str, str], dict[str, object]] | None = None,
        revenue_reporter: Callable[[str, date, str], dict[str, object]] | None = None,
    ) -> None:
        self._tools = {
            "crm.search_companies": ToolSpec(
                name="crm.search_companies",
                version="1",
                argument_model=SearchCompaniesArguments,
                requires_approval=False,
                handler=self._search_companies,
            ),
            "crm.create_company": ToolSpec(
                name="crm.create_company",
                version="1",
                argument_model=CreateCompanyArguments,
                requires_approval=True,
                handler=self._create_company,
            ),
            "crm.create_deal": ToolSpec(
                name="crm.create_deal",
                version="1",
                argument_model=CreateDealArguments,
                requires_approval=True,
                handler=self._create_deal,
            ),
        }
        if prospect_reader is not None:
            self._tools["gtm.inspect_selected_prospect"] = ToolSpec(
                name="gtm.inspect_selected_prospect",
                version="1",
                argument_model=InspectSelectedProspectArguments,
                requires_approval=False,
                handler=lambda tenant_id, arguments: prospect_reader(
                    tenant_id, arguments.campaign_id
                ),
            )
        if prospect_linker is not None:
            self._tools["crm.link_selected_prospect"] = ToolSpec(
                name="crm.link_selected_prospect",
                version="1",
                argument_model=LinkSelectedProspectArguments,
                requires_approval=True,
                handler=lambda tenant_id, arguments: prospect_linker(
                    tenant_id,
                    arguments.campaign_id,
                    arguments.idempotency_key,
                ),
            )
        if revenue_reporter is not None:
            self._tools["crm.revenue_report"] = ToolSpec(
                name="crm.revenue_report",
                version="1",
                argument_model=RevenueReportArguments,
                requires_approval=False,
                handler=lambda tenant_id, arguments: revenue_reporter(
                    tenant_id, arguments.as_of, arguments.currency
                ),
            )
        self._service = service

    def get(self, name: str) -> ToolSpec:
        try:
            return self._tools[name]
        except KeyError as error:
            raise ValueError(f"tool is not allowlisted: {name}") from error

    def _search_companies(
        self, tenant_id: str, arguments: SearchCompaniesArguments
    ) -> dict[str, object]:
        query = arguments.query.casefold()
        companies = [
            company.model_dump(mode="json")
            for company in self._service.list_companies(tenant_id)
            if query in company.name.casefold()
            or query in (company.normalized_domain or "").casefold()
            or query in (company.industry or "").casefold()
        ]
        return {"companies": companies, "count": len(companies)}

    def _create_company(
        self, tenant_id: str, arguments: CreateCompanyArguments
    ) -> dict[str, object]:
        company = CompanyCreate(
            company_id=f"company-{sha256(arguments.idempotency_key.encode()).hexdigest()[:24]}",
            name=arguments.name,
            normalized_domain=arguments.normalized_domain,
            website=arguments.website,
            industry=arguments.industry,
            region=arguments.region,
        )
        return {
            "company": self._service.create_company(tenant_id, company).model_dump(
                mode="json"
            )
        }

    def _create_deal(
        self, tenant_id: str, arguments: CreateDealArguments
    ) -> dict[str, object]:
        deal = DealCreate(
            deal_id=f"deal-{sha256(arguments.idempotency_key.encode()).hexdigest()[:24]}",
            company_id=arguments.company_id,
            contact_id=arguments.contact_id,
            pipeline_id=arguments.pipeline_id,
            stage_id=arguments.stage_id,
            name=arguments.name,
            amount_minor=arguments.amount_minor,
            currency=arguments.currency,
            idempotency_key=arguments.idempotency_key,
        )
        saved = self._service.create_deal(tenant_id, deal)
        return {"deal": saved.model_dump(mode="json")}
