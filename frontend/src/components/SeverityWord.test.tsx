import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import type { components } from '@/types/openapi'
import SeverityWord from './SeverityWord'

type Severity = components['schemas']['Severity']

const SEVERITIES: [Severity, string][] = [
  ['critical', 'Critical'],
  ['high', 'High'],
  ['medium', 'Medium'],
  ['low', 'Low'],
]

describe('SeverityWord', () => {
  it.each(SEVERITIES)('renders %s as a bold plain word', (severity, word) => {
    render(<SeverityWord severity={severity} />)

    const rendered = screen.getByText(word)
    expect(rendered).toBeVisible()
    expect(rendered).toHaveTextContent(new RegExp(`^${word}$`))
    expect(rendered.className).toBe('font-semibold')
    expect(document.body.textContent).toBe(word)
  })

  it.each([[null], [undefined]])(
    'renders the em dash when the severity is %s',
    (severity) => {
      render(<SeverityWord severity={severity} />)

      expect(screen.getByText('—')).toBeVisible()
      expect(document.body.textContent).toBe('—')
    },
  )
})
