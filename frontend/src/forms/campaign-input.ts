import type { CampaignInput } from '../api/campaign'

export type CampaignField =
  | 'product_name'
  | 'product_url'
  | 'short_description'
  | 'known_capabilities'
  | 'known_limitations'
  | 'industries'
  | 'company_size'
  | 'roles'
  | 'pain_hypotheses'

export type CampaignFields = Record<CampaignField, string>
export type FieldErrors = Partial<Record<CampaignField, string>>

export interface ParsedCampaignFields {
  input?: CampaignInput
  errors: FieldErrors
}

export function parseCampaignFields(fields: CampaignFields): ParsedCampaignFields {
  const errors: FieldErrors = {}
  const productName = scalar(fields.product_name, 'Product name', 120, errors, 'product_name')
  const description = scalar(
    fields.short_description,
    'Description',
    1_000,
    errors,
    'short_description',
  )
  const companySize = scalar(
    fields.company_size,
    'Company size',
    120,
    errors,
    'company_size',
  )
  const capabilities = lines(
    fields.known_capabilities,
    'Capabilities',
    24,
    200,
    errors,
    'known_capabilities',
  )
  const limitations = lines(
    fields.known_limitations,
    'Limitations',
    24,
    200,
    errors,
    'known_limitations',
    false,
  )
  const industries = lines(fields.industries, 'Industries', 12, 120, errors, 'industries')
  const roles = lines(fields.roles, 'Roles', 12, 120, errors, 'roles')
  const pains = lines(
    fields.pain_hypotheses,
    'Pain hypotheses',
    12,
    500,
    errors,
    'pain_hypotheses',
  )

  const rawUrl = fields.product_url.trim()
  if (rawUrl) {
    try {
      const url = new URL(rawUrl)
      if (url.protocol !== 'http:' && url.protocol !== 'https:') throw new Error()
    } catch {
      errors.product_url = 'Use a complete http or https URL.'
    }
  }
  if (Object.keys(errors).length > 0) return { errors }
  return {
    errors,
    input: {
      product_name: productName,
      product_url: rawUrl || null,
      short_description: description,
      known_capabilities: capabilities,
      known_limitations: limitations,
      icp: {
        industries,
        company_size: companySize,
        roles,
        pain_hypotheses: pains,
      },
    },
  }
}

function scalar(
  raw: string,
  label: string,
  maximum: number,
  errors: FieldErrors,
  field: CampaignField,
): string {
  const value = raw.trim()
  if (!value) errors[field] = `${label} is required.`
  else if (value.length > maximum) errors[field] = `${label} must be ${maximum} characters or fewer.`
  else if (hasControlCharacter(value)) errors[field] = `${label} contains unsupported control characters.`
  return value
}

function lines(
  raw: string,
  label: string,
  maximumItems: number,
  maximumLength: number,
  errors: FieldErrors,
  field: CampaignField,
  required = true,
): string[] {
  const values = raw.split(/\r?\n/).map((value) => value.trim()).filter(Boolean)
  if (required && values.length === 0) errors[field] = `${label} requires at least one value.`
  else if (values.length > maximumItems) errors[field] = `${label} allows at most ${maximumItems} values.`
  else if (values.some((value) => value.length > maximumLength)) {
    errors[field] = `${label} values must be ${maximumLength} characters or fewer.`
  } else if (values.some(hasControlCharacter)) {
    errors[field] = `${label} contains unsupported control characters.`
  } else if (new Set(values).size !== values.length) {
    errors[field] = `Duplicate ${label.toLowerCase()} are not allowed.`
  }
  return values
}

function hasControlCharacter(value: string): boolean {
  return [...value].some((character) => {
    const code = character.charCodeAt(0)
    return code <= 9 || code === 11 || code === 12 || (code >= 14 && code <= 31) || code === 127
  })
}
