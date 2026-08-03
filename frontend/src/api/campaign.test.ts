import { afterEach, describe, expect, it, vi } from 'vitest'

import { CampaignApiError, createCampaign, submitClaimDecisions } from './campaign'
import type { Campaign, CampaignInput } from './campaign'

const input: CampaignInput = {
  product_name: 'RouteSignal',
  product_url: 'https://example.com',
  short_description: 'Highlights recurring delivery exceptions.',
  known_capabilities: ['exception reporting'],
  known_limitations: ['requires dispatch data'],
  icp: {
    industries: ['logistics'],
    company_size: 'mid-market',
    roles: ['Head of Operations'],
    pain_hypotheses: ['manual exception review'],
  },
}

function campaignResponse(): Campaign {
  return {
    campaign_id: 'campaign-0001',
    state: 'awaiting_claim_approval',
    product: {
      campaign_id: 'campaign-0001',
      product_id: 'product-0001',
      name: 'RouteSignal',
      url: 'https://example.com/',
      short_description: input.short_description,
      capabilities: ['exception reporting'],
      limitations: ['requires dispatch data'],
    },
    icp: {
      campaign_id: 'campaign-0001',
      icp_id: 'icp-0001',
      industries: ['logistics'],
      company_size: 'mid-market',
      roles: ['Head of Operations'],
      pain_hypotheses: ['manual exception review'],
    },
    evidence: [
      {
        evidence_id: 'evidence-0001',
        campaign_id: 'campaign-0001',
        source_kind: 'fixture',
        title: 'Submitted details',
        excerpt: 'Submitted evidence excerpt.',
      },
    ],
    claims: [
      {
        claim_id: 'claim-0001',
        campaign_id: 'campaign-0001',
        product_id: 'product-0001',
        text: 'RouteSignal supports exception reporting.',
        status: 'pending',
        evidence_ids: ['evidence-0001'],
        uncertainty: 'low',
      },
    ],
    approvals: [],
  }
}

afterEach(() => vi.unstubAllGlobals())

describe('campaign API', () => {
  it('posts a campaign and validates the response ownership graph', async () => {
    const response = campaignResponse()
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(response), {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await expect(createCampaign(input)).resolves.toEqual(response)
    expect(fetchMock).toHaveBeenCalledWith('/campaigns', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    })
  })

  it.each([
    ['duplicate evidence IDs', (body: ReturnType<typeof campaignResponse>) => {
      body.evidence.push({ ...body.evidence[0] })
    }],
    ['foreign claim ownership', (body: ReturnType<typeof campaignResponse>) => {
      body.claims[0].campaign_id = 'campaign-9999'
    }],
    ['unresolved claim evidence', (body: ReturnType<typeof campaignResponse>) => {
      body.claims[0].evidence_ids = ['evidence-9999']
    }],
    ['unsafe citation URL', (body: ReturnType<typeof campaignResponse>) => {
      body.evidence[0].canonical_url = 'javascript:alert(1)'
    }],
  ])('rejects %s', async (_label, mutate) => {
    const body = campaignResponse()
    mutate(body)
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status: 201 })),
    )

    await expect(createCampaign(input)).rejects.toThrow('invalid campaign response')
  })

  it('normalizes FastAPI validation errors', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ detail: [{ msg: 'Field required' }, { msg: 'Too long' }] }),
          { status: 422 },
        ),
      ),
    )

    await expect(createCampaign(input)).rejects.toEqual(
      new CampaignApiError('Field required; Too long', 422),
    )
  })

  it('submits exact claim decisions to the owning campaign', async () => {
    const response = campaignResponse()
    response.state = 'awaiting_prospect_selection'
    response.claims[0].status = 'approved'
    response.approvals = [
      {
        approval_id: 'approval-0001',
        campaign_id: 'campaign-0001',
        claim_id: 'claim-0001',
        decision: 'approved',
        original_text: response.claims[0].text,
        reviewed_text: response.claims[0].text,
        evidence_ids: ['evidence-0001'],
        wording_source: 'proposed',
        evidence_attested: false,
      },
    ]
    const decisions = [{ claim_id: 'claim-0001', decision: 'approved' as const }]
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(response), { status: 200 }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await submitClaimDecisions('campaign-0001', decisions)

    expect(fetchMock).toHaveBeenCalledWith(
      '/campaigns/campaign-0001/claim-decisions',
      expect.objectContaining({ body: JSON.stringify({ decisions }) }),
    )
  })
})
