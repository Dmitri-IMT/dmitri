import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import Ornament from './Ornament'

afterEach(() => {
  cleanup()
})

describe('Ornament', () => {
  it('renders three aria-hidden vectors without the Unicode ornament glyph', () => {
    render(<Ornament />)

    const ornament = screen.getByTestId('ornament')
    const vectors = ornament.querySelectorAll(':scope > svg')

    expect(ornament).toHaveAttribute('data-testid', 'ornament')
    expect(ornament).toHaveAttribute('aria-hidden', 'true')
    expect(ornament).toHaveClass(
      'flex',
      'w-full',
      'items-center',
      'gap-2',
      'text-muted-foreground',
    )
    expect(ornament.children).toHaveLength(3)
    expect(vectors).toHaveLength(3)
    expect(ornament.querySelector('title')).not.toBeInTheDocument()
    expect(ornament.querySelector('[role]')).not.toBeInTheDocument()
    expect(ornament).not.toHaveTextContent('\u2766')
  })

  it('stretches both rule vectors and fills them with the current color', () => {
    render(<Ornament />)
    const vectors = screen
      .getByTestId('ornament')
      .querySelectorAll(':scope > svg')
    const rules = [vectors.item(0), vectors.item(2)]

    for (const rule of rules) {
      expect(rule).toHaveClass('h-px', 'flex-1')
      expect(rule).toHaveAttribute('viewBox', '0 0 1 1')
      expect(rule).toHaveAttribute('preserveAspectRatio', 'none')
      expect(rule).toHaveAttribute('focusable', 'false')
      expect(rule.querySelectorAll(':scope > rect')).toHaveLength(1)
      expect(rule.querySelector('rect')).toHaveAttribute('width', '1')
      expect(rule.querySelector('rect')).toHaveAttribute('height', '1')
      expect(rule.querySelector('rect')).toHaveAttribute('fill', 'currentColor')
    }
  })

  it('keeps the lozenge fixed without disabling aspect-ratio preservation', () => {
    render(<Ornament />)
    const lozenge = screen
      .getByTestId('ornament')
      .querySelectorAll(':scope > svg')
      .item(1)

    expect(lozenge).toHaveClass('size-3', 'shrink-0')
    expect(lozenge).toHaveAttribute('viewBox', '0 0 12 12')
    expect(lozenge).not.toHaveAttribute('preserveAspectRatio')
    expect(lozenge).toHaveAttribute('focusable', 'false')
    expect(lozenge.querySelectorAll(':scope > path')).toHaveLength(1)
    expect(lozenge.querySelector('path')).toHaveAttribute(
      'fill',
      'currentColor',
    )
  })
})
