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
  it.each(SEVERITIES)(
    'renders %s with its semantic color',
    (severity, word) => {
      render(<SeverityWord severity={severity} />)

      const rendered = screen.getByText(word)
      expect(rendered).toBeVisible()
      expect(rendered).toHaveTextContent(new RegExp(`^${word}$`))
      expect(rendered).toHaveClass('rounded-full', 'border')
      expect(document.body.textContent).toBe(word)
    },
  )

  it('uses a different color class for each severity', () => {
    const classes = SEVERITIES.map(([severity, word]) => {
      render(<SeverityWord severity={severity} />)
      const className = screen.getByText(word).className
      cleanup()
      return className
    })

    expect(new Set(classes).size).toBe(4)
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
