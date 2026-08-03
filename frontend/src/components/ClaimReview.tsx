import { useEffect, useRef, useState } from 'react'

import type { Campaign, ClaimDecision } from '../api/campaign'

interface ClaimReviewProps {
  campaign: Campaign
  onReview: (decisions: ClaimDecision[]) => Promise<void>
}

interface ReviewState {
  decision: 'approved' | 'rejected' | null
  editing: boolean
  draftText: string
  savedEdit?: string
  attested: boolean
  editError?: string
}

function ClaimReview({ campaign, onReview }: ClaimReviewProps) {
  const [reviews, setReviews] = useState<Record<string, ReviewState>>(() =>
    Object.fromEntries(
      campaign.claims.map((claim) => [
        claim.claim_id,
        { decision: null, editing: false, draftText: claim.text, attested: false },
      ]),
    ),
  )
  const [busy, setBusy] = useState(false)
  const [requestError, setRequestError] = useState('')
  const submitting = useRef(false)
  const headingRef = useRef<HTMLDivElement>(null)
  const pending = campaign.claims.filter((claim) => !reviews[claim.claim_id].decision).length
  const approved = campaign.claims.filter(
    (claim) => reviews[claim.claim_id].decision === 'approved',
  ).length
  const canSubmit = pending === 0 && approved > 0 && !busy

  useEffect(() => headingRef.current?.focus(), [])

  function update(claimId: string, change: Partial<ReviewState>) {
    setReviews((current) => ({
      ...current,
      [claimId]: { ...current[claimId], ...change },
    }))
  }

  async function submitReview() {
    if (!canSubmit || submitting.current) return
    const decisions: ClaimDecision[] = campaign.claims.map((claim) => {
      const review = reviews[claim.claim_id]
      if (review.decision === 'approved' && review.savedEdit) {
        return {
          claim_id: claim.claim_id,
          decision: 'approved',
          edited_text: review.savedEdit,
          evidence_attested: true,
        }
      }
      return { claim_id: claim.claim_id, decision: review.decision! }
    })
    submitting.current = true
    setBusy(true)
    setRequestError('')
    try {
      await onReview(decisions)
    } catch (error) {
      setRequestError(error instanceof Error ? error.message : 'Claim review failed.')
    } finally {
      submitting.current = false
      setBusy(false)
    }
  }

  return (
    <section className="review-workspace" aria-labelledby="profile-heading">
      <div className="section-heading" tabIndex={-1} id="profile-heading" ref={headingRef}>
        <p className="step-label">Step 2 of 2</p>
        <h2>Review the proposed product profile</h2>
        <p>Approve only wording that the supplied evidence supports.</p>
      </div>
      <div className="fixture-notice" role="note">
        Deterministic fixture—not live research. Evidence below comes only from the submitted form.
      </div>

      <div className="profile-grid">
        <article className="profile-card">
          <span className="card-label">Product</span>
          <h3>{campaign.product.name}</h3>
          <p>{campaign.product.short_description}</p>
          <Detail label="Capabilities" values={campaign.product.capabilities} />
          <Detail label="Limitations" values={campaign.product.limitations} empty="None submitted" />
        </article>
        <article className="profile-card">
          <span className="card-label">Ideal customer</span>
          <h3>{campaign.icp.roles.join(', ')}</h3>
          <Detail label="Industries" values={campaign.icp.industries} />
          <Detail label="Company size" values={[campaign.icp.company_size]} />
          <Detail label="Pain hypotheses" values={campaign.icp.pain_hypotheses} />
        </article>
      </div>

      <div className="claims-heading">
        <div>
          <span className="card-label">Authorization boundary</span>
          <h3>Proposed claims</h3>
        </div>
        <span className="claim-count">{campaign.claims.length} to review</span>
      </div>

      <div className="claim-list">
        {campaign.claims.map((claim, index) => {
          const review = reviews[claim.claim_id]
          const evidence = claim.evidence_ids.map((id) =>
            campaign.evidence.find((item) => item.evidence_id === id)!,
          )
          return (
            <fieldset className="claim-card" key={claim.claim_id}>
              <legend>Claim {index + 1}</legend>
              <div className="claim-meta">
                <span className={`uncertainty uncertainty-${claim.uncertainty}`}>
                  {claim.uncertainty} uncertainty
                </span>
                <span className="decision-state">{review.decision ?? 'pending'}</span>
              </div>
              <p className="claim-text">{review.savedEdit ?? claim.text}</p>
              {review.savedEdit && <p className="edited-note">User-edited wording; evidence attested.</p>}
              <div className="evidence-list">
                {evidence.map((item) => (
                  <article key={item.evidence_id} className="evidence-card">
                    <span>Fixture evidence</span>
                    <h4>{item.title}</h4>
                    <p>{item.excerpt}</p>
                  </article>
                ))}
              </div>

              {review.editing && (
                <div className="edit-panel">
                  <label htmlFor={`edit-${claim.claim_id}`}>Edited wording for claim {index + 1}</label>
                  <textarea
                    id={`edit-${claim.claim_id}`}
                    rows={4}
                    maxLength={500}
                    value={review.draftText}
                    aria-describedby={`edit-help-${claim.claim_id}`}
                    onChange={(event) => update(claim.claim_id, {
                      draftText: event.target.value,
                      decision: null,
                      savedEdit: undefined,
                      attested: false,
                      editError: undefined,
                    })}
                  />
                  <p id={`edit-help-${claim.claim_id}`} className="field-help">
                    Changing wording invalidates any earlier decision. Maximum 500 characters.
                  </p>
                  <label className="attestation">
                    <input
                      type="checkbox"
                      checked={review.attested}
                      onChange={(event) => update(claim.claim_id, { attested: event.target.checked })}
                    />
                    I confirm this edited wording is supported by the evidence shown.
                  </label>
                  {review.editError && <p className="field-error">{review.editError}</p>}
                  <div className="edit-actions">
                    <button
                      type="button"
                      className="secondary-action"
                      disabled={!review.attested || !validEdit(review.draftText, claim.text)}
                      onClick={() => update(claim.claim_id, {
                        editing: false,
                        savedEdit: review.draftText.trim(),
                        decision: null,
                        editError: undefined,
                      })}
                    >
                      Save edited wording
                    </button>
                    <button type="button" className="text-action" onClick={() => update(claim.claim_id, {
                      editing: false,
                      draftText: review.savedEdit ?? claim.text,
                      attested: Boolean(review.savedEdit),
                    })}>Cancel edit</button>
                  </div>
                </div>
              )}

              <div className="decision-actions">
                <button
                  type="button"
                  className="approve-action"
                  aria-pressed={review.decision === 'approved'}
                  disabled={review.editing}
                  onClick={() => update(claim.claim_id, { decision: 'approved' })}
                >Approve</button>
                <button
                  type="button"
                  className="reject-action"
                  aria-pressed={review.decision === 'rejected'}
                  onClick={() => update(claim.claim_id, {
                    decision: 'rejected', editing: false, savedEdit: undefined,
                    draftText: claim.text, attested: false,
                  })}
                >Reject</button>
                <button
                  type="button"
                  className="text-action"
                  onClick={() => update(claim.claim_id, {
                    editing: true, decision: null,
                    draftText: review.savedEdit ?? claim.text,
                  })}
                >Edit wording</button>
              </div>
            </fieldset>
          )
        })}
      </div>

      <div className="review-footer">
        <p className="review-status" role="status" aria-live="polite">
          {pending > 0
            ? `${pending} ${pending === 1 ? 'claim still needs' : 'claims still need'} a decision.`
            : approved === 0
              ? 'At least one claim must be approved to continue.'
              : `${approved} approved claim${approved === 1 ? '' : 's'} ready to authorize.`}
        </p>
        {requestError && <p className="message error-message" role="alert">{requestError}</p>}
        <button className="primary-action" type="button" disabled={!canSubmit} onClick={submitReview}>
          {busy ? 'Authorizing…' : 'Authorize reviewed claims'}
        </button>
      </div>
    </section>
  )
}

function validEdit(value: string, original: string): boolean {
  const normalized = value.trim()
  return normalized.length > 0 && normalized.length <= 500 && normalized !== original
}

function Detail({ label, values, empty }: { label: string; values: string[]; empty?: string }) {
  return (
    <div className="profile-detail">
      <strong>{label}</strong>
      <p>{values.length > 0 ? values.join(' · ') : empty}</p>
    </div>
  )
}

export default ClaimReview
