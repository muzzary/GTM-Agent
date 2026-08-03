import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { Campaign } from '../api/campaign'
import * as crmApi from '../api/crm'
import CrmWorkspace from './CrmWorkspace'

vi.mock('../api/crm', async () => {
  const actual = await vi.importActual<typeof crmApi>('../api/crm')
  return {
    ...actual,
    createCrmCompany: vi.fn().mockResolvedValue({ company_id: 'company-0001', name: 'Acme' }),
    createCrmContact: vi.fn().mockResolvedValue({ contact_id: 'contact-0001' }),
    createCrmPipeline: vi.fn().mockResolvedValue({ pipeline_id: 'pipeline-0001', stages: [{ stage_id: 'stage-0001' }] }),
    createCrmDeal: vi.fn().mockResolvedValue({ deal_id: 'deal-0001', name: 'Expansion', amount_minor: 240000, currency: 'USD' }),
    createCrmActivity: vi.fn().mockResolvedValue({ activity_id: 'activity-0001' }),
  }
})

function campaign(): Campaign {
  return {
    campaign_id: 'campaign-0001',
    state: 'prospect_researched',
    product: { campaign_id: 'campaign-0001', product_id: 'product-0001', name: 'RouteSignal', url: null, short_description: 'Operations software.', capabilities: ['reporting'], limitations: [] },
    icp: { campaign_id: 'campaign-0001', icp_id: 'icp-0001', industries: ['logistics'], regions: [], company_size: 'mid-market', roles: ['operations'], pain_hypotheses: ['manual review'] },
    evidence: [], claims: [], approvals: [],
    prospects: [{ prospect_id: 'prospect-0001', campaign_id: 'campaign-0001', company: 'Acme Logistics', industry: 'logistics', region: 'United States', research_run_id: null, provider: 'fixture', official_url: null, matched_icp_fields: [], evidence_ids: [], score: 0.9, evidence_quality: 1, research_completeness: 1, ranking_factors: [], unknown_icp_fields: [], uncertainty: 'low' }],
    selected_prospect_id: 'prospect-0001',
    prospect_research: null,
  }
}

describe('CrmWorkspace', () => {
  it('creates a company, contact, deal, and research activity from a prospect', async () => {
    render(<CrmWorkspace campaign={campaign()} onBack={vi.fn()} />)
    fireEvent.change(screen.getByLabelText('Contact name'), { target: { value: 'Jordan Lee' } })
    fireEvent.change(screen.getByLabelText('Contact role'), { target: { value: 'VP Operations' } })
    fireEvent.change(screen.getByLabelText('Deal name'), { target: { value: 'Expansion' } })
    fireEvent.change(screen.getByLabelText('Deal value (USD)'), { target: { value: '2400' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create company, contact, and deal' }))

    await waitFor(() => expect(screen.getByText('CRM path complete')).toBeInTheDocument())
    expect(crmApi.createCrmActivity).toHaveBeenCalled()
  })
})
