import { useRef, useState } from 'react'
import type { FormEvent } from 'react'

import type { CampaignInput } from '../api/campaign'
import {
  parseCampaignFields,
  type CampaignField,
  type CampaignFields,
  type FieldErrors,
} from '../forms/campaign-input'

interface CampaignFormProps {
  onCreate: (input: CampaignInput) => Promise<void>
}

function CampaignForm({ onCreate }: CampaignFormProps) {
  const [errors, setErrors] = useState<FieldErrors>({})
  const [requestError, setRequestError] = useState('')
  const [busy, setBusy] = useState(false)
  const submitting = useRef(false)
  const summaryRef = useRef<HTMLDivElement>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (submitting.current) return
    const data = new FormData(event.currentTarget)
    const fields = Object.fromEntries(
      [...data.entries()].map(([key, value]) => [key, String(value)]),
    ) as CampaignFields
    const parsed = parseCampaignFields(fields)
    setErrors(parsed.errors)
    setRequestError('')
    if (!parsed.input) {
      requestAnimationFrame(() => summaryRef.current?.focus())
      return
    }

    submitting.current = true
    setBusy(true)
    try {
      await onCreate(parsed.input)
    } catch (error) {
      setRequestError(error instanceof Error ? error.message : 'Campaign creation failed.')
    } finally {
      submitting.current = false
      setBusy(false)
    }
  }

  return (
    <form className="campaign-form" onSubmit={handleSubmit} noValidate>
      <div className="section-heading">
        <p className="step-label">Step 1 of 2</p>
        <h2>Describe the product and buyer</h2>
        <p>Start with what you know. The agent will propose a reviewable profile.</p>
      </div>

      {Object.keys(errors).length > 0 && (
        <div className="message error-message" role="alert" tabIndex={-1} ref={summaryRef}>
          Check the highlighted fields before continuing.
        </div>
      )}
      {requestError && <div className="message error-message" role="alert">{requestError}</div>}

      <fieldset>
        <legend>Product details</legend>
        <TextField name="product_name" label="Product name" help="Up to 120 characters." error={errors.product_name} />
        <TextField name="product_url" label="Product URL" help="Optional. Use a complete http or https URL." error={errors.product_url} type="url" />
        <TextField name="short_description" label="Short description" help="What it does and for whom. Up to 1,000 characters." error={errors.short_description} multiline />
        <TextField name="known_capabilities" label="Known capabilities" help="One capability per line; up to 24." error={errors.known_capabilities} multiline />
        <TextField name="known_limitations" label="Known limitations" help="Optional. One limitation per line; up to 24." error={errors.known_limitations} multiline />
      </fieldset>

      <fieldset>
        <legend>Ideal customer profile</legend>
        <TextField name="industries" label="Industries" help="One industry per line; up to 12." error={errors.industries} multiline />
        <TextField name="regions" label="Regions" help="Optional. One intended country or market region per line; supplied regions become hard live-discovery filters." error={errors.regions} multiline />
        <TextField name="company_size" label="Company size" help="For example: 50–500 employees or mid-market." error={errors.company_size} />
        <TextField name="roles" label="Target roles" help="One buyer role per line; up to 12." error={errors.roles} multiline />
        <TextField name="pain_hypotheses" label="Pain hypotheses" help="One suspected buyer pain per line; up to 12." error={errors.pain_hypotheses} multiline />
      </fieldset>

      <button className="primary-action" type="submit" disabled={busy}>
        {busy ? 'Building fixture profile…' : 'Research product profile'}
      </button>
      <p className="submission-status" role="status" aria-live="polite">
        {busy ? 'Submitting product and ICP details.' : ''}
      </p>
    </form>
  )
}

interface TextFieldProps {
  name: CampaignField
  label: string
  help: string
  error?: string
  multiline?: boolean
  type?: string
}

function TextField({ name, label, help, error, multiline = false, type = 'text' }: TextFieldProps) {
  const helpId = `${name}-help`
  const errorId = `${name}-error`
  const describedBy = error ? `${helpId} ${errorId}` : helpId
  return (
    <div className="field">
      <label htmlFor={name}>{label}</label>
      <p id={helpId} className="field-help">{help}</p>
      {multiline ? (
        <textarea id={name} name={name} rows={3} aria-describedby={describedBy} aria-invalid={Boolean(error)} />
      ) : (
        <input id={name} name={name} type={type} aria-describedby={describedBy} aria-invalid={Boolean(error)} />
      )}
      {error && <p id={errorId} className="field-error">{error}</p>}
    </div>
  )
}

export default CampaignForm
