import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import App from './App'

describe('App', () => {
  it('introduces the product and ICP setup workflow', () => {
    render(<App />)

    expect(
      screen.getByRole('heading', { name: 'Configure your GTM campaign' }),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Product and ICP setup starts in Phase 3.'),
    ).toBeInTheDocument()
  })
})
