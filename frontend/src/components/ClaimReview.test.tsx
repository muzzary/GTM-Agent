import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { Campaign } from '../api/campaign'
import ClaimReview from './ClaimReview'

const campaign: Campaign = {
  campaign_id: 'campaign-0001',
  state: 'awaiting_claim_approval',
  product: {
    product_id: 'product-0001',
    campaign_id: 'campaign-0001',
    name: 'RouteSignal',
    url: null,
    short_description: 'Highlights recurring delivery exceptions.',
    capabilities: ['exception reporting'],
    limitations: ['requires dispatch data'],
  },
  icp: {
    icp_id: 'icp-0001',
    campaign_id: 'campaign-0001',
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
      excerpt: 'Submitted capability evidence.',
    },
    {
      evidence_id: 'evidence-0002',
      campaign_id: 'campaign-0001',
      source_kind: 'fixture',
      title: 'Submitted description',
      excerpt: 'Submitted description evidence.',
    },
  ],
  claims: [
    {
      claim_id: 'claim-0001', campaign_id: 'campaign-0001', product_id: 'product-0001',
      text: 'RouteSignal supports exception reporting.', status: 'pending',
      evidence_ids: ['evidence-0001'], uncertainty: 'low',
    },
    {
      claim_id: 'claim-0002', campaign_id: 'campaign-0001', product_id: 'product-0001',
      text: 'RouteSignal highlights exceptions.', status: 'pending',
      evidence_ids: ['evidence-0002'], uncertainty: 'medium',
    },
  ],
  approvals: [],
}

describe('ClaimReview', () => {
  it('shows fixture provenance and blocks incomplete or all-rejected review', () => {
    render(<ClaimReview campaign={campaign} onReview={vi.fn()} />)

    expect(screen.getByText(/deterministic fixture—not live research/i)).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: 'Review the proposed product profile' }),
    ).toHaveFocus()
    expect(screen.getByRole('button', { name: 'Authorize reviewed claims' })).toBeDisabled()
    expect(screen.getByText(/2 claims still need a decision/i)).toBeInTheDocument()

    fireEvent.click(screen.getAllByRole('button', { name: 'Reject' })[0])
    fireEvent.click(screen.getAllByRole('button', { name: 'Reject' })[1])
    expect(screen.getByText(/at least one claim must be approved/i)).toBeInTheDocument()
  })

  it('requires attestation, then submits exact edited and rejected decisions once', async () => {
    const onReview = vi.fn().mockResolvedValue(undefined)
    render(<ClaimReview campaign={campaign} onReview={onReview} />)

    fireEvent.click(screen.getAllByRole('button', { name: 'Edit wording' })[0])
    const editor = screen.getByLabelText('Edited wording for claim 1')
    fireEvent.change(editor, { target: { value: 'RouteSignal highlights reviewed exceptions.' } })
    expect(screen.getByRole('button', { name: 'Save edited wording' })).toBeDisabled()
    fireEvent.click(screen.getByLabelText(/I confirm this edited wording/i))
    fireEvent.click(screen.getByRole('button', { name: 'Save edited wording' }))
    fireEvent.click(screen.getAllByRole('button', { name: 'Approve' })[0])
    fireEvent.click(screen.getAllByRole('button', { name: 'Reject' })[1])

    const submit = screen.getByRole('button', { name: 'Authorize reviewed claims' })
    fireEvent.click(submit)
    fireEvent.click(submit)

    await waitFor(() => expect(onReview).toHaveBeenCalledTimes(1))
    expect(onReview).toHaveBeenCalledWith([
      {
        claim_id: 'claim-0001',
        decision: 'approved',
        edited_text: 'RouteSignal highlights reviewed exceptions.',
        evidence_attested: true,
      },
      { claim_id: 'claim-0002', decision: 'rejected' },
    ])
  })

  it('returns an approved claim to pending when its edit is reopened', () => {
    render(<ClaimReview campaign={campaign} onReview={vi.fn()} />)
    fireEvent.click(screen.getAllByRole('button', { name: 'Approve' })[0])
    fireEvent.click(screen.getAllByRole('button', { name: 'Reject' })[1])
    expect(screen.getByRole('button', { name: 'Authorize reviewed claims' })).toBeEnabled()

    fireEvent.click(screen.getAllByRole('button', { name: 'Edit wording' })[0])

    expect(screen.getByRole('button', { name: 'Authorize reviewed claims' })).toBeDisabled()
    expect(screen.getByText(/1 claim still needs a decision/i)).toBeInTheDocument()
  })
})
