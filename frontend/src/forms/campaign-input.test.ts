import { describe, expect, it } from 'vitest'

import { parseCampaignFields } from './campaign-input'

const valid = {
  product_name: ' RouteSignal ',
  product_url: 'https://example.com/product',
  short_description: 'Highlights recurring delivery exceptions.',
  known_capabilities: 'exception reporting\nalerts',
  known_limitations: 'requires dispatch data',
  industries: 'logistics\nsupply chain',
  regions: ' United States \nCanada',
  company_size: 'mid-market',
  roles: 'Head of Operations',
  pain_hypotheses: 'manual exception review',
}

describe('campaign form parsing', () => {
  it('trims fields and preserves newline value order', () => {
    const result = parseCampaignFields(valid)

    expect(result.errors).toEqual({})
    expect(result.input?.product_name).toBe('RouteSignal')
    expect(result.input?.known_capabilities).toEqual(['exception reporting', 'alerts'])
    expect(result.input?.icp.industries).toEqual(['logistics', 'supply chain'])
    expect(result.input?.icp.regions).toEqual(['United States', 'Canada'])
  })

  it('rejects duplicates, unsupported URLs, and oversized values', () => {
    const result = parseCampaignFields({
      ...valid,
      product_url: 'ftp://example.com',
      known_capabilities: 'alerts\n alerts ',
      regions: 'Canada\n Canada ',
      roles: 'x'.repeat(121),
    })

    expect(result.errors.product_url).toContain('http')
    expect(result.errors.known_capabilities).toContain('Duplicate')
    expect(result.errors.roles).toContain('120')
    expect(result.errors.regions).toContain('Duplicate')
    expect(result.input).toBeUndefined()
  })
})
