from datetime import date
from hashlib import sha256

from src.data.crm_repository import CrmRepository
from src.schemas.crm import DealStatus
from src.schemas.revenue import (
    RevenueEvent,
    RevenueEventCreate,
    RevenueEventType,
    RevenueMetric,
    RevenueReport,
    RevenueWarning,
    SubscriptionSnapshot,
)


class RevenueService:
    """Stores revenue events and derives deterministic, explainable reports."""

    def __init__(self, repository: CrmRepository) -> None:
        self.repository = repository

    def ingest_event(self, tenant_id: str, payload: RevenueEventCreate) -> RevenueEvent:
        event = RevenueEvent(
            event_id=payload.event_id
            or (
                "revenue-event-"
                f"{sha256(payload.idempotency_key.encode()).hexdigest()[:24]}"
            ),
            tenant_id=tenant_id,
            subscription_id=payload.subscription_id,
            company_id=payload.company_id,
            deal_id=payload.deal_id,
            event_type=payload.event_type,
            effective_at=payload.effective_at,
            recorded_at=payload.recorded_at,
            mrr_minor_after=payload.mrr_minor_after,
            currency=payload.currency,
            idempotency_key=payload.idempotency_key,
        )
        return self.repository.save_revenue_event(event)

    def report(self, tenant_id: str, as_of: date, currency: str) -> RevenueReport:
        events = self.repository.list_revenue_events(tenant_id)
        warnings: list[RevenueWarning] = []
        relevant: list[RevenueEvent] = []
        for event in events:
            if event.currency != currency:
                warnings.append(
                    RevenueWarning(
                        code="currency_mismatch",
                        detail=(
                            f"Event currency {event.currency} was excluded from the "
                            f"{currency} report."
                        ),
                        event_ids=(event.event_id,),
                    )
                )
                continue
            if event.effective_at.date() <= as_of:
                relevant.append(event)
                if event.recorded_at.date() > event.effective_at.date():
                    warnings.append(
                        RevenueWarning(
                            code="late_arrival",
                            detail=(
                                "The event was recorded after its effective date and "
                                "was ordered by effective time."
                            ),
                            event_ids=(event.event_id,),
                        )
                    )

        snapshots: dict[str, SubscriptionSnapshot] = {}
        new_business: list[str] = []
        expansion: list[str] = []
        contraction: list[str] = []
        churn: list[str] = []
        new_amount = expansion_amount = contraction_amount = churn_amount = 0
        for event in sorted(
            relevant,
            key=lambda item: (item.effective_at, item.recorded_at, item.event_id),
        ):
            previous = snapshots.get(event.subscription_id)
            previous_mrr = previous.mrr_minor if previous else 0
            delta = event.mrr_minor_after - previous_mrr
            if previous is None and event.event_type not in {
                RevenueEventType.TRIAL_STARTED,
                RevenueEventType.CONVERTED,
                RevenueEventType.REACTIVATED,
            }:
                warnings.append(
                    RevenueWarning(
                        code="incomplete_history",
                        detail=(
                            "The first observed event is not an activation or trial "
                            "event."
                        ),
                        event_ids=(event.event_id,),
                    )
                )
            if event.event_type is RevenueEventType.CONVERTED and delta <= 0:
                warnings.append(
                    self._inconsistent(event, "conversion must increase MRR")
                )
            elif event.event_type is RevenueEventType.EXPANDED and delta <= 0:
                warnings.append(
                    self._inconsistent(event, "expansion must increase MRR")
                )
            elif (
                event.event_type is RevenueEventType.CONTRACTED
                and not 0 < event.mrr_minor_after < previous_mrr
            ):
                warnings.append(
                    self._inconsistent(
                        event, "contraction must reduce MRR but remain active"
                    )
                )
            elif (
                event.event_type is RevenueEventType.CANCELLED
                and event.mrr_minor_after != 0
            ):
                warnings.append(
                    self._inconsistent(event, "cancellation must set MRR to zero")
                )

            if delta > 0:
                if previous_mrr == 0:
                    new_business.append(event.event_id)
                    new_amount += event.mrr_minor_after
                else:
                    expansion.append(event.event_id)
                    expansion_amount += delta
            elif delta < 0:
                if event.mrr_minor_after == 0:
                    churn.append(event.event_id)
                    churn_amount += abs(delta)
                else:
                    contraction.append(event.event_id)
                    contraction_amount += abs(delta)
            snapshots[event.subscription_id] = SubscriptionSnapshot(
                subscription_id=event.subscription_id,
                company_id=event.company_id,
                as_of=as_of,
                mrr_minor=event.mrr_minor_after,
                currency=currency,
                last_event_id=event.event_id,
            )

        pipeline_value, forecast_value, pipeline_warnings = self._pipeline_metrics(
            tenant_id, currency
        )
        warnings.extend(pipeline_warnings)
        return RevenueReport(
            tenant_id=tenant_id,
            as_of=as_of,
            currency=currency,
            mrr_minor=sum(snapshot.mrr_minor for snapshot in snapshots.values()),
            new_business=RevenueMetric(
                amount_minor=new_amount,
                event_ids=tuple(new_business),
                explanation=(
                    "MRR activated from zero by conversion or reactivation events."
                ),
            ),
            expansion=RevenueMetric(
                amount_minor=expansion_amount,
                event_ids=tuple(expansion),
                explanation=(
                    "Positive MRR changes applied to already-active subscriptions."
                ),
            ),
            contraction=RevenueMetric(
                amount_minor=contraction_amount,
                event_ids=tuple(contraction),
                explanation="Partial MRR reductions that left subscriptions active.",
            ),
            churn=RevenueMetric(
                amount_minor=churn_amount,
                event_ids=tuple(churn),
                explanation=(
                    "MRR removed when subscriptions reached zero through cancellation."
                ),
            ),
            pipeline_value=pipeline_value,
            forecast_value=forecast_value,
            warnings=tuple(warnings),
        )

    def _pipeline_metrics(
        self, tenant_id: str, currency: str
    ) -> tuple[RevenueMetric, RevenueMetric, list[RevenueWarning]]:
        pipeline_amount = forecast_amount = 0
        deal_ids: list[str] = []
        warnings: list[RevenueWarning] = []
        for deal in self.repository.list_deals(tenant_id):
            if deal.status is not DealStatus.OPEN:
                continue
            if deal.currency != currency:
                warnings.append(
                    RevenueWarning(
                        code="pipeline_currency_mismatch",
                        detail=(
                            f"Open deal currency {deal.currency} was excluded from "
                            f"the {currency} pipeline report."
                        ),
                        event_ids=(),
                    )
                )
                continue
            try:
                pipeline = self.repository.get_pipeline(tenant_id, deal.pipeline_id)
                stage = next(
                    item for item in pipeline.stages if item.stage_id == deal.stage_id
                )
            except (LookupError, StopIteration):
                warnings.append(
                    RevenueWarning(
                        code="incomplete_pipeline_data",
                        detail=(
                            f"Deal {deal.deal_id} has no resolvable pipeline stage."
                        ),
                        event_ids=(),
                    )
                )
                continue
            deal_ids.append(deal.deal_id)
            pipeline_amount += deal.amount_minor
            forecast_amount += round(deal.amount_minor * stage.probability)
        return (
            RevenueMetric(
                amount_minor=pipeline_amount,
                event_ids=tuple(deal_ids),
                explanation="Sum of open deals in the requested currency.",
            ),
            RevenueMetric(
                amount_minor=forecast_amount,
                event_ids=tuple(deal_ids),
                explanation=(
                    "Open deal amounts weighted by their pipeline-stage probabilities."
                ),
            ),
            warnings,
        )

    @staticmethod
    def _inconsistent(event: RevenueEvent, detail: str) -> RevenueWarning:
        return RevenueWarning(
            code="inconsistent_event", detail=detail, event_ids=(event.event_id,)
        )
