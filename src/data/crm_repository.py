import sqlite3
from hashlib import sha256
from pathlib import Path
from typing import TypeVar

from src.schemas.crm import Activity, Company, Contact, Deal, Pipeline
from src.schemas.revenue import RevenueEvent


class CrmNotFoundError(LookupError):
    pass


class CrmConflictError(ValueError):
    pass


Record = TypeVar("Record", Company, Contact, Deal, Pipeline)


class CrmRepository:
    """Small SQLite CRM repository with tenant checks at every boundary."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS crm_companies (
                    company_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS crm_contacts (
                    contact_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    company_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS crm_pipelines (
                    pipeline_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS crm_pipeline_stages (
                    stage_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    pipeline_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS crm_deals (
                    deal_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    company_id TEXT NOT NULL,
                    contact_id TEXT,
                    pipeline_id TEXT NOT NULL,
                    stage_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS crm_activities (
                    activity_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS crm_revenue_events (
                    event_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    subscription_id TEXT NOT NULL,
                    effective_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS crm_idempotency (
                    tenant_id TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, operation, idempotency_key)
                );
                CREATE INDEX IF NOT EXISTS idx_crm_companies_tenant
                    ON crm_companies (tenant_id);
                CREATE INDEX IF NOT EXISTS idx_crm_deals_tenant
                    ON crm_deals (tenant_id);
                CREATE INDEX IF NOT EXISTS idx_crm_revenue_events_tenant_time
                    ON crm_revenue_events (tenant_id, effective_at);
                """
            )

    def save_company(self, company: Company) -> Company:
        with self._connect() as connection:
            self._assert_existing_tenant(
                connection,
                "crm_companies",
                "company_id",
                company.company_id,
                company.tenant_id,
            )
            connection.execute(
                """
                INSERT INTO crm_companies (company_id, tenant_id, payload)
                VALUES (?, ?, ?)
                ON CONFLICT(company_id) DO UPDATE SET
                    tenant_id = excluded.tenant_id,
                    payload = excluded.payload
                """,
                (company.company_id, company.tenant_id, company.model_dump_json()),
            )
        return company

    def get_company(self, tenant_id: str, company_id: str) -> Company:
        row = self._get_row("crm_companies", "company_id", tenant_id, company_id)
        return Company.model_validate_json(row[0])

    def list_companies(self, tenant_id: str) -> tuple[Company, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload FROM crm_companies
                WHERE tenant_id = ? ORDER BY company_id
                """,
                (tenant_id,),
            ).fetchall()
        return tuple(Company.model_validate_json(row[0]) for row in rows)

    def find_companies_by_domain(
        self, tenant_id: str, normalized_domain: str
    ) -> tuple[Company, ...]:
        return tuple(
            company
            for company in self.list_companies(tenant_id)
            if company.normalized_domain == normalized_domain
        )

    def save_contact(self, contact: Contact) -> Contact:
        with self._connect() as connection:
            self._assert_related_tenant(
                connection,
                "crm_companies",
                "company_id",
                contact.company_id,
                contact.tenant_id,
                "company",
            )
            self._assert_existing_tenant(
                connection,
                "crm_contacts",
                "contact_id",
                contact.contact_id,
                contact.tenant_id,
            )
            connection.execute(
                """
                INSERT INTO crm_contacts (contact_id, tenant_id, company_id, payload)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(contact_id) DO UPDATE SET
                    tenant_id = excluded.tenant_id,
                    company_id = excluded.company_id,
                    payload = excluded.payload
                """,
                (
                    contact.contact_id,
                    contact.tenant_id,
                    contact.company_id,
                    contact.model_dump_json(),
                ),
            )
        return contact

    def get_contact(self, tenant_id: str, contact_id: str) -> Contact:
        row = self._get_row("crm_contacts", "contact_id", tenant_id, contact_id)
        return Contact.model_validate_json(row[0])

    def save_pipeline(self, pipeline: Pipeline) -> Pipeline:
        with self._connect() as connection:
            self._assert_existing_tenant(
                connection,
                "crm_pipelines",
                "pipeline_id",
                pipeline.pipeline_id,
                pipeline.tenant_id,
            )
            connection.execute(
                """
                INSERT INTO crm_pipelines (pipeline_id, tenant_id, payload)
                VALUES (?, ?, ?)
                ON CONFLICT(pipeline_id) DO UPDATE SET
                    tenant_id = excluded.tenant_id,
                    payload = excluded.payload
                """,
                (pipeline.pipeline_id, pipeline.tenant_id, pipeline.model_dump_json()),
            )
            for stage in pipeline.stages:
                self._assert_existing_tenant(
                    connection,
                    "crm_pipeline_stages",
                    "stage_id",
                    stage.stage_id,
                    pipeline.tenant_id,
                )
                connection.execute(
                    """
                    INSERT INTO crm_pipeline_stages (
                        stage_id, tenant_id, pipeline_id, payload
                    ) VALUES (?, ?, ?, ?)
                    ON CONFLICT(stage_id) DO UPDATE SET
                        tenant_id = excluded.tenant_id,
                        pipeline_id = excluded.pipeline_id,
                        payload = excluded.payload
                    """,
                    (
                        stage.stage_id,
                        stage.tenant_id,
                        stage.pipeline_id,
                        stage.model_dump_json(),
                    ),
                )
        return pipeline

    def get_pipeline(self, tenant_id: str, pipeline_id: str) -> Pipeline:
        row = self._get_row("crm_pipelines", "pipeline_id", tenant_id, pipeline_id)
        return Pipeline.model_validate_json(row[0])

    def save_deal(
        self,
        deal: Deal,
        *,
        idempotency_key: str,
        idempotency_fingerprint: str | None = None,
    ) -> Deal:
        if not idempotency_key.strip() or len(idempotency_key) > 128:
            raise CrmConflictError("idempotency key is required and bounded")
        with self._connect() as connection:
            self._assert_related_tenant(
                connection,
                "crm_companies",
                "company_id",
                deal.company_id,
                deal.tenant_id,
                "company",
            )
            if deal.contact_id is not None:
                self._assert_related_tenant(
                    connection,
                    "crm_contacts",
                    "contact_id",
                    deal.contact_id,
                    deal.tenant_id,
                    "contact",
                )
            self._assert_related_tenant(
                connection,
                "crm_pipelines",
                "pipeline_id",
                deal.pipeline_id,
                deal.tenant_id,
                "pipeline",
            )
            stage = connection.execute(
                """
                SELECT tenant_id, pipeline_id FROM crm_pipeline_stages
                WHERE stage_id = ?
                """,
                (deal.stage_id,),
            ).fetchone()
            if stage is None:
                raise CrmConflictError("deal stage does not exist")
            if stage[0] != deal.tenant_id or stage[1] != deal.pipeline_id:
                raise CrmConflictError(
                    "deal stage must belong to the same tenant and pipeline"
                )

            fingerprint = sha256(
                (idempotency_fingerprint or deal.model_dump_json()).encode()
            ).hexdigest()
            prior = connection.execute(
                """
                SELECT resource_id, fingerprint FROM crm_idempotency
                WHERE tenant_id = ? AND operation = ? AND idempotency_key = ?
                """,
                (deal.tenant_id, "create_deal", idempotency_key),
            ).fetchone()
            if prior is not None:
                if prior[1] != fingerprint:
                    raise CrmConflictError(
                        "idempotency key was reused with different data"
                    )
                return self._get_deal_from_connection(
                    connection, deal.tenant_id, prior[0]
                )

            self._assert_existing_tenant(
                connection, "crm_deals", "deal_id", deal.deal_id, deal.tenant_id
            )
            connection.execute(
                """
                INSERT INTO crm_deals (
                    deal_id, tenant_id, company_id, contact_id, pipeline_id,
                    stage_id, payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(deal_id) DO UPDATE SET
                    tenant_id = excluded.tenant_id,
                    company_id = excluded.company_id,
                    contact_id = excluded.contact_id,
                    pipeline_id = excluded.pipeline_id,
                    stage_id = excluded.stage_id,
                    payload = excluded.payload
                """,
                (
                    deal.deal_id,
                    deal.tenant_id,
                    deal.company_id,
                    deal.contact_id,
                    deal.pipeline_id,
                    deal.stage_id,
                    deal.model_dump_json(),
                ),
            )
            connection.execute(
                """
                INSERT INTO crm_idempotency (
                    tenant_id, operation, idempotency_key, resource_id, fingerprint
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    deal.tenant_id,
                    "create_deal",
                    idempotency_key,
                    deal.deal_id,
                    fingerprint,
                ),
            )
        return deal

    def get_deal(self, tenant_id: str, deal_id: str) -> Deal:
        row = self._get_row("crm_deals", "deal_id", tenant_id, deal_id)
        return Deal.model_validate_json(row[0])

    def list_deals(self, tenant_id: str) -> tuple[Deal, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM crm_deals WHERE tenant_id = ? ORDER BY deal_id",
                (tenant_id,),
            ).fetchall()
        return tuple(Deal.model_validate_json(row[0]) for row in rows)

    def save_revenue_event(self, event: RevenueEvent) -> RevenueEvent:
        if not event.idempotency_key.strip() or len(event.idempotency_key) > 128:
            raise CrmConflictError(
                "revenue event idempotency key is required and bounded"
            )
        payload = event.model_dump_json()
        fingerprint = sha256(
            event.model_dump_json(exclude={"idempotency_key"}).encode()
        ).hexdigest()
        with self._connect() as connection:
            self._assert_related_tenant(
                connection,
                "crm_companies",
                "company_id",
                event.company_id,
                event.tenant_id,
                "company",
            )
            if event.deal_id is not None:
                self._assert_related_tenant(
                    connection,
                    "crm_deals",
                    "deal_id",
                    event.deal_id,
                    event.tenant_id,
                    "deal",
                )
            self._assert_existing_tenant(
                connection,
                "crm_revenue_events",
                "event_id",
                event.event_id,
                event.tenant_id,
            )
            existing = connection.execute(
                "SELECT payload FROM crm_revenue_events WHERE event_id = ?",
                (event.event_id,),
            ).fetchone()
            if existing is not None:
                saved = RevenueEvent.model_validate_json(existing[0])
                if saved.model_dump_json() != payload:
                    raise CrmConflictError(
                        "revenue event ID was reused with different data"
                    )
            prior = connection.execute(
                """
                SELECT resource_id, fingerprint FROM crm_idempotency
                WHERE tenant_id = ? AND operation = ? AND idempotency_key = ?
                """,
                (event.tenant_id, "revenue_event", event.idempotency_key),
            ).fetchone()
            if prior is not None:
                if prior[1] != fingerprint:
                    raise CrmConflictError(
                        "revenue event idempotency key was reused with different data"
                    )
                return self._get_revenue_event_from_connection(
                    connection, event.tenant_id, prior[0]
                )
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO crm_revenue_events (
                        event_id, tenant_id, subscription_id, effective_at, payload
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        event.event_id,
                        event.tenant_id,
                        event.subscription_id,
                        event.effective_at.isoformat(),
                        payload,
                    ),
                )
            connection.execute(
                """
                INSERT INTO crm_idempotency (
                    tenant_id, operation, idempotency_key, resource_id, fingerprint
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    event.tenant_id,
                    "revenue_event",
                    event.idempotency_key,
                    event.event_id,
                    fingerprint,
                ),
            )
        return event

    def list_revenue_events(self, tenant_id: str) -> tuple[RevenueEvent, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload FROM crm_revenue_events
                WHERE tenant_id = ? ORDER BY effective_at, event_id
                """,
                (tenant_id,),
            ).fetchall()
        return tuple(RevenueEvent.model_validate_json(row[0]) for row in rows)

    def get_revenue_event(self, tenant_id: str, event_id: str) -> RevenueEvent:
        with self._connect() as connection:
            return self._get_revenue_event_from_connection(
                connection, tenant_id, event_id
            )

    def save_activity(self, activity: Activity) -> Activity:
        table = {
            "company": "crm_companies",
            "contact": "crm_contacts",
            "deal": "crm_deals",
        }[activity.entity_type.value]
        id_column = {
            "company": "company_id",
            "contact": "contact_id",
            "deal": "deal_id",
        }[activity.entity_type.value]
        with self._connect() as connection:
            self._assert_related_tenant(
                connection,
                table,
                id_column,
                activity.entity_id,
                activity.tenant_id,
                activity.entity_type.value,
            )
            self._assert_existing_tenant(
                connection,
                "crm_activities",
                "activity_id",
                activity.activity_id,
                activity.tenant_id,
            )
            connection.execute(
                """
                INSERT INTO crm_activities (
                    activity_id, tenant_id, entity_type, entity_id,
                    occurred_at, payload
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(activity_id) DO UPDATE SET
                    tenant_id = excluded.tenant_id,
                    entity_type = excluded.entity_type,
                    entity_id = excluded.entity_id,
                    occurred_at = excluded.occurred_at,
                    payload = excluded.payload
                """,
                (
                    activity.activity_id,
                    activity.tenant_id,
                    activity.entity_type.value,
                    activity.entity_id,
                    activity.occurred_at.isoformat(),
                    activity.model_dump_json(),
                ),
            )
        return activity

    def list_activities(
        self, tenant_id: str, entity_type: str, entity_id: str
    ) -> tuple[Activity, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload FROM crm_activities
                WHERE tenant_id = ? AND entity_type = ? AND entity_id = ?
                ORDER BY occurred_at, activity_id
                """,
                (tenant_id, entity_type, entity_id),
            ).fetchall()
        return tuple(Activity.model_validate_json(row[0]) for row in rows)

    def _get_deal_from_connection(
        self, connection: sqlite3.Connection, tenant_id: str, deal_id: str
    ) -> Deal:
        row = connection.execute(
            "SELECT payload FROM crm_deals WHERE deal_id = ? AND tenant_id = ?",
            (deal_id, tenant_id),
        ).fetchone()
        if row is None:
            raise CrmConflictError("idempotency record points to a missing deal")
        return Deal.model_validate_json(row[0])

    def _get_revenue_event_from_connection(
        self, connection: sqlite3.Connection, tenant_id: str, event_id: str
    ) -> RevenueEvent:
        row = connection.execute(
            """
            SELECT payload FROM crm_revenue_events
            WHERE event_id = ? AND tenant_id = ?
            """,
            (event_id, tenant_id),
        ).fetchone()
        if row is None:
            raise CrmNotFoundError(f"revenue event not found: {event_id}")
        return RevenueEvent.model_validate_json(row[0])

    def _get_row(
        self, table: str, id_column: str, tenant_id: str, record_id: str
    ) -> tuple[str]:
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT payload FROM {table} WHERE {id_column} = ? AND tenant_id = ?",
                (record_id, tenant_id),
            ).fetchone()
        if row is None:
            raise CrmNotFoundError(f"CRM record not found: {record_id}")
        return row

    @staticmethod
    def _assert_existing_tenant(
        connection: sqlite3.Connection,
        table: str,
        id_column: str,
        record_id: str,
        tenant_id: str,
    ) -> None:
        row = connection.execute(
            f"SELECT tenant_id FROM {table} WHERE {id_column} = ?",
            (record_id,),
        ).fetchone()
        if row is not None and row[0] != tenant_id:
            raise CrmConflictError("CRM record belongs to a different tenant")

    @staticmethod
    def _assert_related_tenant(
        connection: sqlite3.Connection,
        table: str,
        id_column: str,
        record_id: str,
        tenant_id: str,
        label: str,
    ) -> None:
        row = connection.execute(
            f"SELECT tenant_id FROM {table} WHERE {id_column} = ?",
            (record_id,),
        ).fetchone()
        if row is None:
            raise CrmConflictError(f"{label} does not exist")
        if row[0] != tenant_id:
            raise CrmConflictError(f"{label} must belong to the same tenant")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection
