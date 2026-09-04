import { describe, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
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
  it.each(SEVERITIES)('renders %s as the bare word %s', (severity, word) => {
    render(<SeverityWord severity={severity} />)

    const rendered = screen.getByText(word)
    expect(rendered).toBeVisible()
    expect(rendered).toHaveTextContent(new RegExp(`^${word}$`))
    expect(rendered.outerHTML).toMatch(
      new RegExp(`^<span[^>]*>${word}</span>$`),
    )
    expect(document.body.textContent).toBe(word)
  })

  it('presents all four severities identically apart from the word', () => {
    const shapes = SEVERITIES.map(([severity, word]) => {
      render(<SeverityWord severity={severity} />)
      const markup = document.body.innerHTML.replace(word, '')
      cleanup()
      return markup
    })

    expect(new Set(shapes).size).toBe(1)
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
