import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import CampaignForm from './CampaignForm'

function fillRequiredFields(): void {
  fireEvent.change(screen.getByLabelText('Product name'), { target: { value: 'RouteSignal' } })
  fireEvent.change(screen.getByLabelText('Short description'), {
    target: { value: 'Highlights recurring delivery exceptions.' },
  })
  fireEvent.change(screen.getByLabelText('Known capabilities'), {
    target: { value: 'exception reporting' },
  })
  fireEvent.change(screen.getByLabelText('Industries'), { target: { value: 'logistics' } })
  fireEvent.change(screen.getByLabelText('Regions'), { target: { value: 'United States' } })
  fireEvent.change(screen.getByLabelText('Company size'), { target: { value: 'mid-market' } })
  fireEvent.change(screen.getByLabelText('Target roles'), {
    target: { value: 'Head of Operations' },
  })
  fireEvent.change(screen.getByLabelText('Pain hypotheses'), {
    target: { value: 'manual exception review' },
  })
}

describe('CampaignForm', () => {
  it('links errors, focuses the summary, and retains entered values', async () => {
    render(<CampaignForm onCreate={vi.fn()} />)
    fireEvent.change(screen.getByLabelText('Product name'), { target: { value: 'RouteSignal' } })

    fireEvent.click(screen.getByRole('button', { name: 'Research product profile' }))

    const summary = await screen.findByRole('alert')
    expect(summary).toHaveFocus()
    expect(screen.getByLabelText('Product name')).toHaveValue('RouteSignal')
    expect(screen.getByLabelText('Short description')).toHaveAttribute(
      'aria-describedby',
      expect.stringContaining('short_description-error'),
    )
  })

  it('submits a normalized backend-compatible payload once', async () => {
    const onCreate = vi.fn().mockResolvedValue(undefined)
    render(<CampaignForm onCreate={onCreate} />)
    fillRequiredFields()
    fireEvent.change(screen.getByLabelText('Known capabilities'), {
      target: { value: ' reporting \n alerts ' },
    })

    const submit = screen.getByRole('button', { name: 'Research product profile' })
    fireEvent.click(submit)
    fireEvent.click(submit)

    await waitFor(() => expect(onCreate).toHaveBeenCalledTimes(1))
    expect(onCreate.mock.calls[0][0].known_capabilities).toEqual(['reporting', 'alerts'])
    expect(onCreate.mock.calls[0][0].icp.regions).toEqual(['United States'])
  })

  it('announces server errors without clearing the form', async () => {
    const onCreate = vi.fn().mockRejectedValue(new Error('Backend unavailable'))
    render(<CampaignForm onCreate={onCreate} />)
    fillRequiredFields()

    fireEvent.click(screen.getByRole('button', { name: 'Research product profile' }))

    expect(await screen.findByText('Backend unavailable')).toBeInTheDocument()
    expect(screen.getByLabelText('Product name')).toHaveValue('RouteSignal')
  })
})
