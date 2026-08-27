import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import StatusPill, { type StatusPillTone } from './StatusPill'

describe('StatusPill', () => {
  it.each<[StatusPillTone, string, string]>([
    ['running', 'Running…', 'border-input'],
    ['failed', 'Failed', 'border-sev-critical'],
    ['neutral', 'Completed', 'border-border'],
  ])('renders the %s tone with its label', (tone, label, toneClass) => {
    render(<StatusPill tone={tone} label={label} />)

    const pill = screen.getByText(label)

    expect(pill).toHaveClass('border', toneClass)
    expect(pill.className).not.toMatch(/\bbg-/)
  })
})
