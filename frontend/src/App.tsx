import { useState } from 'react'

import { createCampaign, submitClaimDecisions } from './api/campaign'
import type { Campaign, CampaignInput, ClaimDecision } from './api/campaign'
import CampaignForm from './components/CampaignForm'
import ClaimReview from './components/ClaimReview'
import ResearchWorkspace from './components/ResearchWorkspace'

const researchStates = [
  'awaiting_prospect_selection',
  'awaiting_prospect_research',
  'prospect_researched',
]

function App() {
  const [campaign, setCampaign] = useState<Campaign | null>(null)
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
        {campaign && researchStates.includes(campaign.state) && (
          <ResearchWorkspace campaign={campaign} onChange={setCampaign} />
        )}
      </div>
    </main>
  )
}

export default App
