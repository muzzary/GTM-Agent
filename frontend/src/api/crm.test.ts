import { describe, expect, it, vi } from 'vitest'

import { createCrmCompany } from './crm'

describe('CRM API', () => {
  it('sends the tenant boundary and parses a company response', async () => {
    const response = {
      company_id: 'company-0001',
      tenant_id: 'tenant-0001',
      name: 'Acme Logistics',
    }
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response(JSON.stringify(response), { status: 201 }),
    ))

    await expect(createCrmCompany('tenant-0001', { name: 'Acme Logistics' })).resolves.toMatchObject(response)
    expect(fetch).toHaveBeenCalledWith('/crm/companies', expect.objectContaining({
      headers: {
        'Content-Type': 'application/json',
        'X-Tenant-ID': 'tenant-0001',
      },
    }))
  })
})
