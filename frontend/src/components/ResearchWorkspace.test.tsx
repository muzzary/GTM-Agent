import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { Campaign } from '../api/campaign'
import ResearchWorkspace from './ResearchWorkspace'

function researchCampaign(): Campaign {
  return {
    campaign_id: 'campaign-0001',
    state: 'awaiting_prospect_selection',
    product: {
      campaign_id: 'campaign-0001',
      product_id: 'product-0001',
      name: 'RouteSignal',
      url: null,
      short_description: 'Operations software.',
      capabilities: ['exception reporting'],
      limitations: [],
    },
    icp: {
      campaign_id: 'campaign-0001',
      icp_id: 'icp-0001',
      industries: ['logistics'],
      company_size: 'mid-market',
      roles: ['operations'],
      pain_hypotheses: ['manual review'],
    },
    evidence: [{
      evidence_id: 'evidence-0001',
      campaign_id: 'campaign-0001',
      source_kind: 'fixture',
      title: 'Synthetic evidence',
      excerpt: 'Workflow-only prospect evidence.',
    }],
    claims: [],
    approvals: [],
    prospects: [{
      prospect_id: 'prospect-0001',
      campaign_id: 'campaign-0001',
      company: 'Logistics Fixture One',
      industry: 'logistics',
      research_run_id: null,
      provider: 'fixture',
      official_url: null,
      matched_icp_fields: ['industry'],
      evidence_ids: ['evidence-0001'],
      score: 0.9,
      evidence_quality: 0.4,
      research_completeness: 0.2,
      ranking_factors: [],
      unknown_icp_fields: ['company_size'],
      uncertainty: 'high',
    }],
    selected_prospect_id: null,
    prospect_research: null,
  }
}

describe('ResearchWorkspace', () => {
  it('labels fixture prospects and shows transparent ranking measures', () => {
    render(<ResearchWorkspace campaign={researchCampaign()} onChange={vi.fn()} />)

    expect(screen.getByText(/Synthetic candidates are for workflow testing/)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Logistics Fixture One' })).toBeInTheDocument()
    expect(screen.getByText('90')).toBeInTheDocument()
    expect(screen.getByText('40%')).toBeInTheDocument()
    expect(screen.getByText('20%')).toBeInTheDocument()
  })

  it('rejects non-HTTPS seed URLs before making a request', () => {
    render(<ResearchWorkspace campaign={researchCampaign()} onChange={vi.fn()} />)
    fireEvent.change(screen.getByLabelText('Approved public seed URLs'), {
      target: { value: 'http://directory.example/vendors' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Run live market discovery' }))

    expect(screen.getByRole('alert')).toHaveTextContent('public HTTPS URLs')
  })
})
