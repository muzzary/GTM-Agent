export interface CrmCompany {
  company_id: string
  tenant_id: string
  name: string
  normalized_domain: string | null
  website: string | null
  industry: string | null
  region: string | null
  custom_fields: Record<string, string>
  source_prospect_id: string | null
  source_campaign_id: string | null
  source_evidence_ids: string[]
  created_at: string
  updated_at: string
}

export interface CrmPipelineStage {
  stage_id: string
  pipeline_id: string
  tenant_id: string
  name: string
  position: number
  probability: number
}

export interface CrmPipeline {
  pipeline_id: string
  tenant_id: string
  name: string
  stages: CrmPipelineStage[]
}

export interface CrmContact {
  contact_id: string
  company_id: string
  tenant_id: string
  full_name: string
  role: string
  business_email: string | null
  custom_fields: Record<string, string>
  created_at: string
  updated_at: string
}

export interface CrmDeal {
  deal_id: string
  company_id: string
  contact_id: string | null
  pipeline_id: string
  stage_id: string
  tenant_id: string
  name: string
  status: 'open' | 'won' | 'lost'
  amount_minor: number
  currency: string
  custom_fields: Record<string, string>
  created_at: string
  updated_at: string
}

export interface CrmActivity {
  activity_id: string
  tenant_id: string
  entity_type: 'company' | 'contact' | 'deal'
  entity_id: string
  activity_type: 'note' | 'research' | 'outreach' | 'deal_stage_changed'
  summary: string
  occurred_at: string
}

export interface CreateCrmCompanyInput {
  company_id?: string
  name: string
  normalized_domain?: string | null
  website?: string | null
  industry?: string | null
  region?: string | null
  source_prospect_id?: string | null
  source_campaign_id?: string | null
  source_evidence_ids?: string[]
}

export interface CreateCrmContactInput {
  contact_id?: string
  company_id: string
  full_name: string
  role: string
}

export interface CreateCrmPipelineInput {
  pipeline_id?: string
  name: string
  stages: Array<{
    stage_id?: string
    name: string
    position: number
    probability: number
  }>
}

export interface CreateCrmDealInput {
  deal_id?: string
  company_id: string
  contact_id?: string | null
  pipeline_id: string
  stage_id: string
  name: string
  amount_minor: number
  currency: string
  idempotency_key: string
}

export async function createCrmCompany(
  tenantId: string,
  input: CreateCrmCompanyInput,
): Promise<CrmCompany> {
  return requestCrm('/crm/companies', tenantId, input, 201, parseCompany)
}

export async function createCrmContact(
  tenantId: string,
  input: CreateCrmContactInput,
): Promise<CrmContact> {
  return requestCrm('/crm/contacts', tenantId, input, 201, parseContact)
}

export async function createCrmPipeline(
  tenantId: string,
  input: CreateCrmPipelineInput,
): Promise<CrmPipeline> {
  return requestCrm('/crm/pipelines', tenantId, input, 201, parsePipeline)
}

export async function createCrmDeal(
  tenantId: string,
  input: CreateCrmDealInput,
): Promise<CrmDeal> {
  return requestCrm('/crm/deals', tenantId, input, 201, parseDeal)
}

export async function createCrmActivity(
  tenantId: string,
  input: Omit<CrmActivity, 'activity_id' | 'tenant_id'>,
): Promise<CrmActivity> {
  return requestCrm('/crm/activities', tenantId, input, 201, parseActivity)
}

async function requestCrm<T>(
  path: string,
  tenantId: string,
  body: unknown,
  expectedStatus: number,
  parse: (value: unknown) => T,
): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Tenant-ID': tenantId,
      },
      body: JSON.stringify(body),
    })
  } catch {
    throw new Error('Could not reach the CRM API. Check that the backend is running.')
  }
  const payload: unknown = await response.json().catch(() => null)
  if (!response.ok || response.status !== expectedStatus) {
    throw new Error(errorMessage(payload))
  }
  return parse(payload)
}

function parseCompany(value: unknown): CrmCompany {
  if (!isRecord(value) || typeof value.company_id !== 'string') throw new Error('Invalid CRM company response.')
  return value as unknown as CrmCompany
}

function parseContact(value: unknown): CrmContact {
  if (!isRecord(value) || typeof value.contact_id !== 'string') throw new Error('Invalid CRM contact response.')
  return value as unknown as CrmContact
}

function parsePipeline(value: unknown): CrmPipeline {
  if (!isRecord(value) || typeof value.pipeline_id !== 'string' || !Array.isArray(value.stages)) throw new Error('Invalid CRM pipeline response.')
  return value as unknown as CrmPipeline
}

function parseDeal(value: unknown): CrmDeal {
  if (!isRecord(value) || typeof value.deal_id !== 'string') throw new Error('Invalid CRM deal response.')
  return value as unknown as CrmDeal
}

function parseActivity(value: unknown): CrmActivity {
  if (!isRecord(value) || typeof value.activity_id !== 'string') throw new Error('Invalid CRM activity response.')
  return value as unknown as CrmActivity
}

function errorMessage(value: unknown): string {
  if (isRecord(value) && typeof value.detail === 'string') return value.detail
  return 'The CRM API could not complete the request.'
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}
