import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Disclosure from './Disclosure'

function renderDisclosure() {
  render(
    <Disclosure
      label="What's recorded?"
      testId="activity-disclosure"
      caretTestId="activity-caret"
    >
      <p data-testid="activity-note">Recorded activity details.</p>
    </Disclosure>,
  )

  return {
    trigger: screen.getByTestId('activity-disclosure'),
    caret: screen.getByTestId('activity-caret'),
    note: screen.getByTestId('activity-note'),
  }
}

describe('Disclosure', () => {
  it('is collapsed by default and links the trigger to the hidden content', () => {
    const { trigger, note } = renderDisclosure()

    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    expect(trigger).toHaveAttribute('aria-controls', note.id)
    expect(note.id).not.toBe('')
    expect(note).toHaveAttribute('hidden')
    expect(note).not.toBeVisible()
  })

  it('reveals and hides the linked content by click without changing the linkage', async () => {
    const user = userEvent.setup()
    const { trigger, note } = renderDisclosure()
    const controlledId = trigger.getAttribute('aria-controls')

    await user.click(trigger)

    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    expect(trigger).toHaveAttribute('aria-controls', controlledId)
    expect(note).toHaveAttribute('id', controlledId)
    expect(note).toHaveTextContent('Recorded activity details.')
    expect(note).toBeVisible()

    await user.click(trigger)

    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    expect(trigger).toHaveAttribute('aria-controls', controlledId)
    expect(note).toHaveAttribute('id', controlledId)
    expect(note).not.toBeVisible()
  })

  it.each([
    ['Enter', '{Enter}'],
    ['Space', ' '],
  ])('toggles aria-expanded with %s', async (_key, key) => {
    const user = userEvent.setup()
    const { trigger } = renderDisclosure()

    await user.tab()
    expect(trigger).toHaveFocus()

    await user.keyboard(key)
    expect(trigger).toHaveAttribute('aria-expanded', 'true')

    await user.keyboard(key)
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
  })

  it('keeps the label inside the trigger as a plain button', () => {
    const { trigger } = renderDisclosure()

    expect(trigger).toHaveAttribute('type', 'button')
    expect(trigger).toContainElement(screen.getByText("What's recorded?"))
    expect(trigger).toHaveAttribute('data-variant', 'link')
  })

  it('opens with focus on the trigger and marks the open state', async () => {
    const user = userEvent.setup()
    const { trigger, caret } = renderDisclosure()

    await user.tab()
    await user.keyboard('{Enter}')

    expect(trigger).toHaveFocus()
    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    expect(trigger).toHaveAttribute('data-state', 'open')
    expect(caret).toHaveAttribute('aria-hidden', 'true')
  })
})
