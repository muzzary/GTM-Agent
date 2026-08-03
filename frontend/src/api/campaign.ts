export type ApprovalDecision = 'approved' | 'rejected'
export type CampaignState =
  | 'awaiting_claim_approval'
  | 'awaiting_prospect_selection'
  | 'awaiting_prospect_research'
  | 'prospect_researched'
  | 'draft_ready'

export interface CampaignInput {
  product_name: string
  product_url: string | null
  short_description: string
  known_capabilities: string[]
  known_limitations: string[]
  icp: {
    industries: string[]
    regions: string[]
    company_size: string
    roles: string[]
    pain_hypotheses: string[]
  }
}

export interface ClaimDecision {
  claim_id: string
  decision: ApprovalDecision
  edited_text?: string
  evidence_attested?: boolean
}

export interface EvidenceRecord {
  evidence_id: string
  campaign_id: string
  source_kind:
    | 'fixture'
    | 'structured_public'
    | 'official_website'
    | 'approved_market_source'
  provider?: string
  canonical_url?: string | null
  retrieval_url?: string | null
  title: string
  excerpt: string
}

export interface RankingFactor {
  factor_id: string
  icp_field: string
  target: string
  observed_value: string | null
  evidence_ids: string[]
  weight: number
  match: 'matched' | 'not_matched' | 'unknown'
  explanation: string
}

export interface ProspectCandidate {
  prospect_id: string
  campaign_id: string
  company: string
  industry: string
  region: string | null
  research_run_id: string | null
  provider: string
  official_url: string | null
  matched_icp_fields: string[]
  evidence_ids: string[]
  score: number
  evidence_quality: number
  research_completeness: number
  ranking_factors: RankingFactor[]
  unknown_icp_fields: string[]
  uncertainty: 'low' | 'medium' | 'high'
}

export interface ProspectResearchProfile {
  profile_id: string
  prospect_id: string
  research_run_id: string
  evidence_ids: string[]
  covered_sections: string[]
  unknown_sections: string[]
  evidence_quality: number
  research_completeness: number
}

export interface ResearchRun {
  run_id: string
  request_id: string
  campaign_id: string
  stage: 'discovery' | 'prospect'
  status: 'completed' | 'failed'
  warnings: string[]
  failure_code: string | null
}

export interface ResearchOutcome {
  run: ResearchRun
  campaign: Campaign
}

export interface ProductClaim {
  claim_id: string
  campaign_id: string
  product_id: string
  text: string
  status: 'pending' | 'approved' | 'rejected'
  evidence_ids: string[]
  uncertainty: 'low' | 'medium' | 'high'
}

export interface ApprovalRecord {
  approval_id: string
  campaign_id: string
  claim_id: string
  decision: ApprovalDecision
  original_text: string
  reviewed_text: string
  evidence_ids: string[]
  wording_source: 'proposed' | 'user_edited'
  evidence_attested: boolean
}

export interface Campaign {
  campaign_id: string
  state: CampaignState
  product: {
    product_id: string
    campaign_id: string
    name: string
    url: string | null
    short_description: string
    capabilities: string[]
    limitations: string[]
  }
  icp: {
    icp_id: string
    campaign_id: string
    industries: string[]
    regions: string[]
    company_size: string
    roles: string[]
    pain_hypotheses: string[]
  }
  evidence: EvidenceRecord[]
  claims: ProductClaim[]
  approvals: ApprovalRecord[]
  prospects?: ProspectCandidate[]
  research_runs?: ResearchRun[]
  selected_prospect_id?: string | null
  prospect_research?: ProspectResearchProfile | null
}

export class CampaignApiError extends Error {
  readonly status: number | null

  constructor(message: string, status: number | null = null) {
    super(message)
    this.name = 'CampaignApiError'
    this.status = status
  }
}

export async function createCampaign(input: CampaignInput): Promise<Campaign> {
  return requestCampaign('/campaigns', input, 201)
}

export async function submitClaimDecisions(
  campaignId: string,
  decisions: ClaimDecision[],
): Promise<Campaign> {
  return requestCampaign(
    `/campaigns/${encodeURIComponent(campaignId)}/claim-decisions`,
    { decisions },
    200,
  )
}

export async function runDiscovery(
  campaignId: string,
  requestId: string,
  marketSeedUrls: string[],
): Promise<ResearchOutcome> {
  return requestJson(
    `/campaigns/${encodeURIComponent(campaignId)}/discovery-runs`,
    { request_id: requestId, market_seed_urls: marketSeedUrls },
    200,
    parseResearchOutcome,
  )
}

export async function selectProspect(
  campaignId: string,
  prospectId: string,
): Promise<Campaign> {
  return requestJson(
    `/campaigns/${encodeURIComponent(campaignId)}/prospects/${encodeURIComponent(prospectId)}/select`,
    undefined,
    200,
    parseCampaign,
  )
}

export async function researchProspect(
  campaignId: string,
  prospectId: string,
  requestId: string,
): Promise<ResearchOutcome> {
  return requestJson(
    `/campaigns/${encodeURIComponent(campaignId)}/prospects/${encodeURIComponent(prospectId)}/research-runs`,
    { request_id: requestId },
    200,
    parseResearchOutcome,
  )
}

async function requestCampaign(
  path: string,
  body: unknown,
  expectedStatus: number,
): Promise<Campaign> {
  return requestJson(path, body, expectedStatus, parseCampaign)
}

async function requestJson<T>(
  path: string,
  body: unknown,
  expectedStatus: number,
  parse: (value: unknown) => T,
): Promise<T> {
  let response: Response
  try {
    const options: RequestInit = { method: 'POST' }
    if (body !== undefined) {
      options.headers = { 'Content-Type': 'application/json' }
      options.body = JSON.stringify(body)
    }
    response = await fetch(path, {
      ...options,
    })
  } catch {
    throw new CampaignApiError(
      'Could not reach the GTM API. Check that the backend is running.',
    )
  }

  const payload: unknown = await response.json().catch(() => null)
  if (!response.ok || response.status !== expectedStatus) {
    throw new CampaignApiError(errorMessage(payload), response.status)
  }
  return parse(payload)
}

export function parseResearchOutcome(value: unknown): ResearchOutcome {
  if (!isRecord(value)) throw new CampaignApiError('The GTM API returned an invalid research response.')
  const campaign = parseCampaign(value.campaign)
  const run = validateResearchRun(value.run, campaign.campaign_id)
  if (!(campaign.research_runs ?? []).some((item) => item.run_id === run.run_id)) {
    throw new CampaignApiError('The GTM API returned an unresolved research run.')
  }
  return { run, campaign }
}

function errorMessage(payload: unknown): string {
  if (!isRecord(payload)) return 'The GTM API returned an unreadable error.'
  if (typeof payload.detail === 'string') return payload.detail
  if (Array.isArray(payload.detail)) {
    const messages = payload.detail.flatMap((item) =>
      isRecord(item) && typeof item.msg === 'string' ? [item.msg] : [],
    )
    if (messages.length > 0) return messages.join('; ')
  }
  return 'The GTM API could not complete the request.'
}

export function parseCampaign(value: unknown): Campaign {
  try {
    validateCampaign(value)
    return value
  } catch {
    throw new CampaignApiError('The GTM API returned an invalid campaign response.')
  }
}

function validateCampaign(value: unknown): asserts value is Campaign {
  assertRecord(value)
  const campaignId = text(value.campaign_id, 80)
  if (
    value.state !== 'awaiting_claim_approval' &&
    value.state !== 'awaiting_prospect_selection' &&
    value.state !== 'awaiting_prospect_research' &&
    value.state !== 'prospect_researched' &&
    value.state !== 'draft_ready'
  ) {
    throw new Error('unsupported state')
  }

  assertRecord(value.product)
  const productId = text(value.product.product_id, 80)
  owned(value.product, campaignId)
  text(value.product.name, 120)
  nullableText(value.product.url, 2_000)
  text(value.product.short_description, 1_000)
  texts(value.product.capabilities, 24, 200)
  texts(value.product.limitations, 24, 200)

  assertRecord(value.icp)
  owned(value.icp, campaignId)
  text(value.icp.icp_id, 80)
  texts(value.icp.industries, 12, 120)
  texts(value.icp.regions, 12, 120)
  text(value.icp.company_size, 120)
  texts(value.icp.roles, 12, 120)
  texts(value.icp.pain_hypotheses, 12, 500)

  if (!Array.isArray(value.evidence) || !Array.isArray(value.claims)) throw new Error()
  if (!Array.isArray(value.approvals)) throw new Error()
  const evidenceIds = new Set<string>()
  for (const evidence of value.evidence) {
    assertRecord(evidence)
    owned(evidence, campaignId)
    const id = text(evidence.evidence_id, 80)
    unique(evidenceIds, id)
    if (!['fixture', 'structured_public', 'official_website', 'approved_market_source'].includes(String(evidence.source_kind))) throw new Error()
    if (evidence.provider !== undefined) text(evidence.provider, 80)
    if (evidence.canonical_url !== undefined) nullableHttpsUrl(evidence.canonical_url)
    text(evidence.title, 200)
    text(evidence.excerpt, 1_000)
  }

  const claims = new Map<string, Record<string, unknown>>()
  for (const claim of value.claims) {
    assertRecord(claim)
    owned(claim, campaignId)
    if (claim.product_id !== productId) throw new Error()
    const id = text(claim.claim_id, 80)
    if (claims.has(id)) throw new Error()
    claims.set(id, claim)
    text(claim.text, 500)
    if (!['pending', 'approved', 'rejected'].includes(String(claim.status))) throw new Error()
    if (!['low', 'medium', 'high'].includes(String(claim.uncertainty))) throw new Error()
    const references = texts(claim.evidence_ids, 12, 80)
    if (references.length === 0 || references.some((id) => !evidenceIds.has(id))) throw new Error()
  }

  const approvalIds = new Set<string>()
  const approvedClaims = new Set<string>()
  const reviewedClaims = new Set<string>()
  for (const approval of value.approvals) {
    assertRecord(approval)
    owned(approval, campaignId)
    unique(approvalIds, text(approval.approval_id, 80))
    const claimId = text(approval.claim_id, 80)
    const claim = claims.get(claimId)
    if (!claim || reviewedClaims.has(claimId)) throw new Error()
    reviewedClaims.add(claimId)
    if (approval.decision !== 'approved' && approval.decision !== 'rejected') throw new Error()
    if (approval.original_text !== claim.text) throw new Error()
    text(approval.reviewed_text, 500)
    const references = texts(approval.evidence_ids, 12, 80)
    if (JSON.stringify(references) !== JSON.stringify(claim.evidence_ids)) throw new Error()
    if (approval.wording_source !== 'proposed' && approval.wording_source !== 'user_edited') throw new Error()
    if (typeof approval.evidence_attested !== 'boolean') throw new Error()
    if (approval.decision === 'approved') {
      if (claim.status !== 'approved') throw new Error()
      approvedClaims.add(claimId)
    } else if (claim.status !== 'rejected') throw new Error()
    if (approval.wording_source === 'proposed') {
      if (approval.reviewed_text !== approval.original_text || approval.evidence_attested) throw new Error()
    } else if (
      approval.decision !== 'approved' ||
      approval.reviewed_text === approval.original_text ||
      !approval.evidence_attested
    ) throw new Error()
  }
  if (value.state === 'awaiting_claim_approval') {
    if (value.approvals.length !== 0) throw new Error()
    if (value.claims.some((claim) => claim.status !== 'pending')) throw new Error()
  }
  if (value.state === 'awaiting_prospect_selection') {
    if (value.approvals.length !== value.claims.length || approvedClaims.size === 0) throw new Error()
  }

  if (value.prospects !== undefined) {
    if (!Array.isArray(value.prospects)) throw new Error()
    for (const prospect of value.prospects) validateProspect(prospect, campaignId, evidenceIds)
  }
  if (value.research_runs !== undefined) {
    if (!Array.isArray(value.research_runs)) throw new Error()
    value.research_runs.map((run) => validateResearchRun(run, campaignId))
  }
  if (value.selected_prospect_id !== undefined) nullableText(value.selected_prospect_id, 80)
  if (value.prospect_research !== undefined && value.prospect_research !== null) {
    assertRecord(value.prospect_research)
    owned(value.prospect_research, campaignId)
    text(value.prospect_research.profile_id, 80)
    text(value.prospect_research.prospect_id, 80)
    text(value.prospect_research.research_run_id, 80)
    const profileEvidence = texts(value.prospect_research.evidence_ids, 36, 80)
    if (profileEvidence.some((id) => !evidenceIds.has(id))) throw new Error()
    texts(value.prospect_research.covered_sections, 12, 200)
    texts(value.prospect_research.unknown_sections, 12, 200)
    ratio(value.prospect_research.evidence_quality)
    ratio(value.prospect_research.research_completeness)
  }
}

function validateProspect(value: unknown, campaignId: string, evidenceIds: Set<string>): ProspectCandidate {
  assertRecord(value)
  owned(value, campaignId)
  text(value.prospect_id, 80)
  text(value.company, 160)
  text(value.industry, 120)
  nullableText(value.region, 120)
  nullableText(value.research_run_id, 80)
  text(value.provider, 80)
  nullableHttpsUrl(value.official_url)
  texts(value.matched_icp_fields, 12, 80)
  const references = texts(value.evidence_ids, 12, 80)
  if (references.some((id) => !evidenceIds.has(id))) throw new Error()
  ratio(value.score)
  ratio(value.evidence_quality)
  ratio(value.research_completeness)
  if (!['low', 'medium', 'high'].includes(String(value.uncertainty))) throw new Error()
  texts(value.unknown_icp_fields, 12, 80)
  if (!Array.isArray(value.ranking_factors)) throw new Error()
  for (const factor of value.ranking_factors) {
    assertRecord(factor)
    text(factor.factor_id, 80)
    text(factor.icp_field, 63)
    text(factor.target, 200)
    nullableText(factor.observed_value, 200)
    texts(factor.evidence_ids, 12, 80)
    ratio(factor.weight)
    if (!['matched', 'not_matched', 'unknown'].includes(String(factor.match))) throw new Error()
    text(factor.explanation, 1_000)
  }
  return value as unknown as ProspectCandidate
}

function validateResearchRun(value: unknown, campaignId: string): ResearchRun {
  assertRecord(value)
  owned(value, campaignId)
  text(value.run_id, 80)
  text(value.request_id, 96)
  if (value.stage !== 'discovery' && value.stage !== 'prospect') throw new Error()
  if (value.status !== 'completed' && value.status !== 'failed') throw new Error()
  texts(value.warnings, 16, 1_000)
  nullableText(value.failure_code, 63)
  return value as unknown as ResearchRun
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function assertRecord(value: unknown): asserts value is Record<string, unknown> {
  if (!isRecord(value)) throw new Error('expected object')
}

function owned(value: Record<string, unknown>, campaignId: string): void {
  if (value.campaign_id !== campaignId) throw new Error('foreign campaign owner')
}

function text(value: unknown, maximum: number): string {
  if (typeof value !== 'string' || value.length < 1 || value.length > maximum) throw new Error()
  return value
}

function nullableText(value: unknown, maximum: number): void {
  if (value !== null) text(value, maximum)
}

function nullableHttpsUrl(value: unknown): void {
  if (value === null) return
  const candidate = text(value, 2_000)
  if (new URL(candidate).protocol !== 'https:') throw new Error()
}

function ratio(value: unknown): void {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0 || value > 1) throw new Error()
}

function texts(value: unknown, maximumItems: number, maximumLength: number): string[] {
  if (!Array.isArray(value) || value.length > maximumItems) throw new Error()
  const result = value.map((item) => text(item, maximumLength))
  if (new Set(result).size !== result.length) throw new Error()
  return result
}

function unique(values: Set<string>, value: string): void {
  if (values.has(value)) throw new Error()
  values.add(value)
}
