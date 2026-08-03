import { useState } from 'react'
import type { FormEvent } from 'react'

import type { Campaign } from '../api/campaign'
import {
  createCrmActivity,
  createCrmCompany,
  createCrmContact,
  createCrmDeal,
  createCrmPipeline,
} from '../api/crm'
import type { CrmCompany, CrmDeal } from '../api/crm'

interface Props {
  campaign: Campaign
  onBack: () => void
}

const TENANT_ID = 'tenant-demo-0001'

function CrmWorkspace({ campaign, onBack }: Props) {
  const prospect = campaign.prospects?.find(
    (item) => item.prospect_id === campaign.selected_prospect_id,
  )
  const [company, setCompany] = useState<CrmCompany | null>(null)
  const [deal, setDeal] = useState<CrmDeal | null>(null)
  const [contactName, setContactName] = useState('')
  const [contactRole, setContactRole] = useState('')
  const [dealName, setDealName] = useState('')
  const [amount, setAmount] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!prospect) {
    return <section className="crm-workspace"><p className="message error-message">Select a researched prospect before opening CRM.</p></section>
  }
  const selectedProspect = prospect

  async function provisionCrmPath(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!contactName.trim() || !contactRole.trim() || !dealName.trim() || !amount) {
      setError('Complete the contact and deal fields before saving.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const createdCompany = company ?? await createCrmCompany(TENANT_ID, {
        name: selectedProspect.company,
        website: selectedProspect.official_url,
        industry: selectedProspect.industry,
        region: selectedProspect.region,
        source_prospect_id: selectedProspect.prospect_id,
        source_campaign_id: campaign.campaign_id,
        source_evidence_ids: selectedProspect.evidence_ids,
      })
      setCompany(createdCompany)
      const contact = await createCrmContact(TENANT_ID, {
        company_id: createdCompany.company_id,
        full_name: contactName,
        role: contactRole,
      })
      const pipeline = await createCrmPipeline(TENANT_ID, {
        name: 'New business',
        stages: [
          { name: 'Qualified', position: 1, probability: 0.35 },
          { name: 'Proposal', position: 2, probability: 0.65 },
        ],
      })
      const createdDeal = await createCrmDeal(TENANT_ID, {
        company_id: createdCompany.company_id,
        contact_id: contact.contact_id,
        pipeline_id: pipeline.pipeline_id,
        stage_id: pipeline.stages[0].stage_id,
        name: dealName,
        amount_minor: Math.round(Number(amount) * 100),
        currency: 'USD',
        idempotency_key: `deal-${createdCompany.company_id}-${dealName}`,
      })
      await createCrmActivity(TENANT_ID, {
        entity_type: 'deal',
        entity_id: createdDeal.deal_id,
        activity_type: 'research',
        summary: 'Created from approved GTM prospect research.',
        occurred_at: new Date().toISOString(),
      })
      setDeal(createdDeal)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'CRM setup could not be completed.')
    } finally {
      setBusy(false)
    }
  }

  return <section className="crm-workspace" aria-labelledby="crm-heading">
    <div className="section-heading">
      <button className="text-action" type="button" onClick={onBack}>Back to prospect research</button>
      <p className="step-label">CRM · First vertical slice</p>
      <h2 id="crm-heading">Turn verified research into a deal.</h2>
      <p>CRM records retain the selected prospect context. Every write is tenant-scoped and uses the same service boundary an agent will call later.</p>
    </div>
    {error && <p className="message error-message" role="alert">{error}</p>}
    {deal ? <div className="crm-success" role="status">
      <p className="card-label">CRM path complete</p>
      <h3>{company?.name}</h3>
      <p>{deal.name} · ${(deal.amount_minor / 100).toLocaleString()} {deal.currency}</p>
      <p className="muted-copy">Company, contact, pipeline, deal, and research activity were created.</p>
    </div> : <form className="crm-form" onSubmit={provisionCrmPath}>
      <div className="crm-context"><span className="card-label">Verified prospect</span><strong>{prospect.company}</strong><span>{prospect.industry}{prospect.region ? ` · ${prospect.region}` : ''}</span></div>
      <label htmlFor="crm-contact-name">Contact name</label>
      <input id="crm-contact-name" value={contactName} onChange={(event) => setContactName(event.target.value)} placeholder="Jordan Lee" />
      <label htmlFor="crm-contact-role">Contact role</label>
      <input id="crm-contact-role" value={contactRole} onChange={(event) => setContactRole(event.target.value)} placeholder="VP Operations" />
      <label htmlFor="crm-deal-name">Deal name</label>
      <input id="crm-deal-name" value={dealName} onChange={(event) => setDealName(event.target.value)} placeholder="Operations expansion" />
      <label htmlFor="crm-deal-amount">Deal value (USD)</label>
      <input id="crm-deal-amount" type="number" min="0" step="0.01" value={amount} onChange={(event) => setAmount(event.target.value)} placeholder="2400" />
      <button className="primary-action" type="submit" disabled={busy}>{busy ? 'Saving CRM records…' : 'Create company, contact, and deal'}</button>
    </form>}
  </section>
}

export default CrmWorkspace
