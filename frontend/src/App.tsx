import { useEffect, useRef, useState } from 'react'

import { createCampaign, submitClaimDecisions } from './api/campaign'
import type { Campaign, CampaignInput, ClaimDecision } from './api/campaign'
import CampaignForm from './components/CampaignForm'
import ClaimReview from './components/ClaimReview'

function App() {
  const [campaign, setCampaign] = useState<Campaign | null>(null)
  const stepHeading = useRef<HTMLHeadingElement>(null)

  useEffect(() => {
    if (campaign) stepHeading.current?.focus()
  }, [campaign])

  async function handleCreate(input: CampaignInput) {
    setCampaign(await createCampaign(input))
  }

  async function handleReview(decisions: ClaimDecision[]) {
    if (!campaign) return
    setCampaign(await submitClaimDecisions(campaign.campaign_id, decisions))
  }

  return (
    <main className="app-shell">
      <header className="masthead">
        <a className="brand" href="#main-workflow" aria-label="GTM Agent home">
          <span className="brand-mark">G</span>
          <span>GTM Agent</span>
        </a>
        <span className="environment-tag">Local review workspace</span>
      </header>

      <div className="hero" id="main-workflow">
        <p className="eyebrow">Evidence before outreach</p>
        <h1>Build a campaign you can defend.</h1>
        <p className="hero-summary">
          Shape the product profile, inspect every source, and explicitly authorize
          the claims your agent may use.
        </p>
      </div>

      <div className="workflow-panel">
        {!campaign && <CampaignForm onCreate={handleCreate} />}
        {campaign?.state === 'awaiting_claim_approval' && (
          <ClaimReview campaign={campaign} onReview={handleReview} />
        )}
        {campaign?.state === 'awaiting_prospect_selection' && (
          <section className="completion" aria-labelledby="completion-heading">
            <span className="completion-mark" aria-hidden="true">✓</span>
            <p className="step-label">Onboarding complete</p>
            <h2 id="completion-heading" tabIndex={-1} ref={stepHeading}>
              Claims locked. Prospecting is next.
            </h2>
            <p>
              The campaign is now awaiting prospect selection. Phase 4 can use only
              the reviewed wording recorded below.
            </p>
            <div className="approval-ledger">
              {campaign.approvals.map((approval) => (
                <article key={approval.approval_id}>
                  <span className={`ledger-decision ledger-${approval.decision}`}>
                    {approval.decision}
                  </span>
                  <p>{approval.reviewed_text}</p>
                  <small>{approval.wording_source === 'user_edited' ? 'User edited · evidence attested' : 'Proposed wording'}</small>
                </article>
              ))}
            </div>
            <button className="secondary-action" type="button" onClick={() => setCampaign(null)}>
              Start another campaign
            </button>
          </section>
        )}
      </div>
    </main>
  )
}

export default App
