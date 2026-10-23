import { describe, expect, it } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import ChatAnswer from './ChatAnswer'

describe('ChatAnswer', () => {
  it('draws paragraphs, bold words, numbered steps and bullet lists', () => {
    const { container } = render(
      <ChatAnswer
        text={
          'The camera needs **new firmware**.\n\n1. Download it.\n2. Install it.\n\n- Ask your IT person.'
        }
      />,
    )

    expect(screen.getByText('new firmware').tagName).toBe('STRONG')
    const steps = container.querySelector('ol')!
    expect(
      within(steps)
        .getAllByRole('listitem')
        .map((item) => item.textContent),
    ).toEqual(['Download it.', 'Install it.'])
    expect(container.querySelector('ul li')).toHaveTextContent(
      'Ask your IT person.',
    )
  })

  it('links only http and https sources, in a new tab', () => {
    render(
      <ChatAnswer text="Read the advisory ([vendor.example.com](https://vendor.example.com/a)) or [this](javascript:alert(1))." />,
    )

    const link = screen.getByRole('link', { name: 'vendor.example.com' })
    expect(link).toHaveAttribute('href', 'https://vendor.example.com/a')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noreferrer noopener')
    expect(screen.getAllByRole('link')).toHaveLength(1)
  })

  it('shows HTML as plain text', () => {
    render(<ChatAnswer text="<img src=x onerror=alert(1)> stays text" />)

    expect(
      screen.getByText('<img src=x onerror=alert(1)> stays text'),
    ).toBeVisible()
    expect(document.querySelector('img')).toBeNull()
  })
})
