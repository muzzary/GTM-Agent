import { useEffect, useMemo, useRef, useState } from 'react'

import {
  CampaignApiError,
  researchProspect,
  runDiscovery,
  selectProspect,
} from '../api/campaign'
import type { Campaign, EvidenceRecord, ProspectCandidate } from '../api/campaign'

interface Props {
  campaign: Campaign
  onChange: (campaign: Campaign) => void
}

const newRequestId = () =>
  `research-request-${crypto.randomUUID().replaceAll('-', '')}`

function ResearchWorkspace({ campaign, onChange }: Props) {
  const [seedText, setSeedText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const heading = useRef<HTMLHeadingElement>(null)
  const prospects = campaign.prospects ?? []
  const evidence = useMemo(
    () => new Map(campaign.evidence.map((item) => [item.evidence_id, item])),
    [campaign.evidence],
  )
  const selected = prospects.find(
    (item) => item.prospect_id === campaign.selected_prospect_id,
  )

  useEffect(() => {
    heading.current?.focus()
  }, [campaign.state])

  async function execute(action: () => Promise<Campaign>) {
    setBusy(true)
    setError(null)
    try {
      onChange(await action())
    } catch (caught) {
      setError(
        caught instanceof CampaignApiError
          ? caught.message
          : 'The research request could not be completed.',
      )
    } finally {
      setBusy(false)
    }
  }

  async function discover() {
    const seeds = seedText.split(/\r?\n/).map((item) => item.trim()).filter(Boolean)
    if (seeds.length > 10 || seeds.some((item) => !isHttpsUrl(item))) {
      setError('Enter no more than 10 public HTTPS URLs, one per line.')
      return
    }
    await execute(async () => (
      await runDiscovery(campaign.campaign_id, newRequestId(), seeds)
    ).campaign)
  }

  async function choose(prospectId: string) {
    await execute(() => selectProspect(campaign.campaign_id, prospectId))
  }

  async function research() {
    if (!selected) return
    await execute(async () => (
      await researchProspect(
        campaign.campaign_id,
        selected.prospect_id,
        newRequestId(),
      )
    ).campaign)
  }

  return (
    <section className="research-workspace" aria-labelledby="research-heading">
      <div className="section-heading">
        <p className="step-label">Phase 4 · Public research</p>
        <h2 id="research-heading" ref={heading} tabIndex={-1}>Find the fit. Then verify the company.</h2>
        <p>
          Discovery ranks public evidence against the ICP. Outreach remains locked
          until the selected company has a completed research profile.
        </p>
      </div>
      {error && <p className="message error-message" role="alert">{error}</p>}
      {busy && <p className="submission-status" role="status">Research is running. Bounded source rules and rate limits apply.</p>}

      {campaign.state === 'awaiting_prospect_selection' && <>
        <div className="seed-panel">
          <h3>Market discovery sources</h3>
          <p>Optional public directories, associations, registries, or market pages. Wikidata is one source, not the whole research surface.</p>
          <label htmlFor="market-seeds">Approved public seed URLs</label>
          <textarea id="market-seeds" rows={3} value={seedText} onChange={(event) => setSeedText(event.target.value)} placeholder={'https://association.example/members\nhttps://registry.example/market'} />
          <button className="primary-action" type="button" disabled={busy} onClick={discover}>Run live market discovery</button>
        </div>
        {prospects.some((item) => item.provider === 'fixture') && <p className="fixture-notice">Synthetic candidates are for workflow testing. Run live discovery before treating a prospect as researched.</p>}
        <CandidateList prospects={prospects} evidence={evidence} busy={busy} onChoose={choose} />
      </>}

      {campaign.state === 'awaiting_prospect_research' && selected && <div className="research-gate">
        <p className="card-label">Selected prospect</p>
        <h3>{selected.company}</h3>
        <p>Selection does not authorize outreach. Inspect the official site, products, projects, initiatives, news, and technical material first.</p>
        <button className="primary-action" type="button" disabled={busy} onClick={research}>Research selected company</button>
      </div>}

      {campaign.state === 'prospect_researched' && campaign.prospect_research && <ResearchProfile campaign={campaign} evidence={evidence} selected={selected} />}
    </section>
  )
}

function CandidateList({ prospects, evidence, busy, onChoose }: { prospects: ProspectCandidate[]; evidence: Map<string, EvidenceRecord>; busy: boolean; onChoose: (id: string) => void }) {
  if (prospects.length === 0) return <p className="empty-state" role="status">No candidates yet. Add relevant market pages or run structured discovery.</p>
  return <div className="prospect-list">{prospects.map((prospect) => <article className="prospect-card" key={prospect.prospect_id}>
    <div className="prospect-title"><div><p className="card-label">{prospect.provider.replaceAll('_', ' ')}</p><h3>{prospect.company}</h3><p>{prospect.industry}</p></div><strong>{Math.round(prospect.score * 100)}<small>/100 priority</small></strong></div>
    <dl className="score-strip"><div><dt>Evidence</dt><dd>{percent(prospect.evidence_quality)}</dd></div><div><dt>Coverage</dt><dd>{percent(prospect.research_completeness)}</dd></div><div><dt>Uncertainty</dt><dd>{prospect.uncertainty}</dd></div></dl>
    {prospect.ranking_factors.length > 0 && <ul className="factor-list">{prospect.ranking_factors.map((factor) => <li key={factor.factor_id}><span>{factor.icp_field.replaceAll('_', ' ')}</span><strong>{factor.match.replaceAll('_', ' ')}</strong></li>)}</ul>}
    <EvidenceLinks ids={prospect.evidence_ids} evidence={evidence} />
    <button className="secondary-action" type="button" disabled={busy} onClick={() => onChoose(prospect.prospect_id)}>Select and deep research</button>
  </article>)}</div>
}

function ResearchProfile({ campaign, evidence, selected }: { campaign: Campaign; evidence: Map<string, EvidenceRecord>; selected?: ProspectCandidate }) {
  const profile = campaign.prospect_research!
  return <div className="research-profile"><p className="card-label">Research gate complete</p><h3>{selected?.company ?? 'Selected company'}</h3><p className="phase-stop">Phase 4 stops here. The evidence profile is ready for later positioning; no outreach has been generated.</p><dl className="score-strip"><div><dt>Evidence quality</dt><dd>{percent(profile.evidence_quality)}</dd></div><div><dt>Research coverage</dt><dd>{percent(profile.research_completeness)}</dd></div></dl><div className="section-ledger"><div><h4>Covered</h4><p>{profile.covered_sections.join(', ')}</p></div><div><h4>Still unknown</h4><p>{profile.unknown_sections.join(', ') || 'No required sections are unknown.'}</p></div></div><EvidenceLinks ids={profile.evidence_ids} evidence={evidence} /></div>
}

function EvidenceLinks({ ids, evidence }: { ids: string[]; evidence: Map<string, EvidenceRecord> }) {
  return <ul className="citation-list">{ids.flatMap((id) => { const item = evidence.get(id); return item ? [<li key={id}>{item.canonical_url ? <a href={item.canonical_url} target="_blank" rel="noreferrer noopener">{item.title}</a> : <span>{item.title}</span>}<small>{item.source_kind.replaceAll('_', ' ')} · {item.excerpt}</small></li>] : [] })}</ul>
}

function isHttpsUrl(value: string): boolean {
  try { return new URL(value).protocol === 'https:' } catch { return false }
}

const percent = (value: number) => `${Math.round(value * 100)}%`

export default ResearchWorkspace
