import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import App from './App'

describe('App', () => {
  it('starts with the product and ICP configuration workflow', () => {
    render(<App />)

    expect(
      screen.getByRole('heading', { name: 'Build a campaign you can defend.' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: 'Describe the product and buyer' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Research product profile' }),
    ).toBeEnabled()
  })
})
