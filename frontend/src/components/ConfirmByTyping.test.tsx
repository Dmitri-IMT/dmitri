import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ConfirmByTyping from './ConfirmByTyping'

const expectedValue = 'ana@northwind.example'

const baseProps = {
  open: true,
  onOpenChange: () => {},
  heading: 'Delete your account?',
  body: "Your account is deleted and you lose access straight away. This can't be undone.",
  expectedValue,
  confirmLabel: 'Delete my account',
  confirmPendingLabel: 'Deleting…',
  onConfirm: async () => {},
}

type Overrides = Partial<typeof baseProps> & { error?: string | null }

function renderDialog(overrides: Overrides = {}) {
  const props = { ...baseProps, ...overrides }
  const utils = render(<ConfirmByTyping {...props} />)
  return {
    ...utils,
    rerenderDialog: (next: Overrides) =>
      utils.rerender(<ConfirmByTyping {...props} {...next} />),
  }
}

function dialog() {
  return screen.getByTestId('confirm-by-typing-dialog')
}

function submit() {
  return screen.getByTestId('confirm-by-typing-submit')
}

describe('ConfirmByTyping', () => {
  it('renders nothing while closed', () => {
    renderDialog({ open: false })

    expect(screen.queryByRole('dialog')).toBeNull()
  })

  it('names itself from the heading, describes itself from the body, and points the confirming action at the prompt that labels the field', () => {
    renderDialog()

    expect(
      screen.getByRole('dialog', { name: 'Delete your account?' }),
    ).toBeInTheDocument()
    expect(dialog()).toHaveTextContent(
      /Your account is deleted and you lose access straight away\./,
    )

    const prompt = screen.getByTestId('confirm-by-typing-prompt')
    expect(prompt).toHaveTextContent(`Type ${expectedValue} to confirm.`)
    expect(screen.getByLabelText(`Type ${expectedValue} to confirm.`)).toBe(
      screen.getByTestId('confirm-by-typing-input'),
    )
    expect(submit()).toHaveAttribute('aria-describedby', prompt.id)
  })

  it('moves focus into the confirmation field when it opens (DESIGN 5.1)', async () => {
    renderDialog()

    await waitFor(() =>
      expect(screen.getByTestId('confirm-by-typing-input')).toHaveFocus(),
    )
  })

  it.each([
    ['empty', ''],
    ['partial', 'ana@'],
    ['a different address', 'someone.else@northwind.example'],
  ])(
    'holds the confirming action greyed, out of the tab order and unable to request anything while the typed value is %s',
    async (_label, typed) => {
      const user = userEvent.setup()
      const onConfirm = vi.fn(async () => {})
      renderDialog({ onConfirm })

      const input = screen.getByTestId('confirm-by-typing-input')
      if (typed) {
        await user.type(input, typed)
      }

      expect(submit()).toBeDisabled()
      expect(submit()).not.toHaveAttribute('aria-disabled')
      expect(submit()).toHaveAccessibleName('Delete my account')

      await user.click(submit())
      input.focus()
      await user.keyboard('{Enter}')
      await user.tab()

      expect(onConfirm).not.toHaveBeenCalled()
      expect(screen.getByTestId('confirm-by-typing-cancel')).toHaveFocus()
      expect(dialog()).toBeInTheDocument()
    },
  )

  it.each([
    ['the exact address', expectedValue],
    ['a differently cased spelling', 'ANA@Northwind.Example'],
    ['a pasted address with surrounding whitespace', `  ${expectedValue}  `],
  ])(
    'goes live and requests the action exactly once for %s',
    async (_label, typed) => {
      const user = userEvent.setup()
      const onConfirm = vi.fn(async () => {})
      renderDialog({ onConfirm })

      await user.type(screen.getByTestId('confirm-by-typing-input'), typed)
      expect(submit()).toBeEnabled()

      await user.click(submit())

      expect(onConfirm).toHaveBeenCalledTimes(1)
    },
  )

  it('puts the confirming action back into the tab order at the match, after Cancel', async () => {
    const user = userEvent.setup()
    renderDialog()

    const input = screen.getByTestId('confirm-by-typing-input')
    await user.type(input, expectedValue)
    input.focus()

    await user.tab()
    expect(screen.getByTestId('confirm-by-typing-cancel')).toHaveFocus()
    await user.tab()
    expect(submit()).toHaveFocus()
  })

  it('holds the confirming action while the request is outstanding, and a second activation sends nothing more', async () => {
    const user = userEvent.setup()
    let release = () => {}
    const onConfirm = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          release = resolve
        }),
    )
    renderDialog({ onConfirm })

    await user.type(
      screen.getByTestId('confirm-by-typing-input'),
      expectedValue,
    )
    await user.click(submit())

    expect(submit()).toBeDisabled()
    expect(submit()).toHaveAccessibleName('Deleting…')
    expect(screen.queryByTestId('confirm-by-typing-cancel')).toBeNull()

    await user.click(submit())
    expect(onConfirm).toHaveBeenCalledTimes(1)

    release()
    await waitFor(() => expect(submit()).toBeEnabled())
    expect(submit()).toHaveAccessibleName('Delete my account')
    expect(screen.getByTestId('confirm-by-typing-cancel')).toBeInTheDocument()
  })

  it.each([
    [
      'Cancel',
      async (user: ReturnType<typeof userEvent.setup>) =>
        user.click(screen.getByTestId('confirm-by-typing-cancel')),
    ],
    [
      'Escape',
      async (user: ReturnType<typeof userEvent.setup>) =>
        user.keyboard('{Escape}'),
    ],
  ])('requests nothing when dismissed with %s', async (_label, dismiss) => {
    const user = userEvent.setup()
    const onConfirm = vi.fn(async () => {})
    const onOpenChange = vi.fn()
    renderDialog({ onConfirm, onOpenChange })

    await user.type(
      screen.getByTestId('confirm-by-typing-input'),
      expectedValue,
    )
    await dismiss(user)

    expect(onOpenChange).toHaveBeenCalledWith(false)
    expect(onConfirm).not.toHaveBeenCalled()
  })

  it('reopens clean after a dismissal: the field is empty and the confirming action is held again', async () => {
    const user = userEvent.setup()
    const onConfirm = vi.fn(async () => {})

    function Harness() {
      const [open, setOpen] = useState(false)
      return (
        <>
          <button type="button" onClick={() => setOpen(true)}>
            Delete my account
          </button>
          <ConfirmByTyping
            {...baseProps}
            open={open}
            onOpenChange={setOpen}
            onConfirm={onConfirm}
          />
        </>
      )
    }
    render(<Harness />)

    const opener = screen.getByRole('button', { name: 'Delete my account' })
    await user.click(opener)
    await user.type(
      screen.getByTestId('confirm-by-typing-input'),
      expectedValue,
    )
    expect(submit()).toBeEnabled()

    await user.click(screen.getByTestId('confirm-by-typing-cancel'))
    await waitFor(() =>
      expect(screen.queryByTestId('confirm-by-typing-dialog')).toBeNull(),
    )

    await user.click(opener)
    expect(screen.getByTestId('confirm-by-typing-input')).toHaveValue('')
    expect(submit()).toBeDisabled()
    expect(onConfirm).not.toHaveBeenCalled()
  })

  it('returns focus to the opener on dismissal while the opener is still mounted', async () => {
    const user = userEvent.setup()

    function Harness() {
      const [open, setOpen] = useState(false)
      return (
        <>
          <button type="button" onClick={() => setOpen(true)}>
            Delete my account
          </button>
          <ConfirmByTyping {...baseProps} open={open} onOpenChange={setOpen} />
        </>
      )
    }
    render(<Harness />)

    const opener = screen.getByRole('button', { name: 'Delete my account' })
    await user.click(opener)
    await user.keyboard('{Escape}')

    await waitFor(() => expect(opener).toHaveFocus())
  })

  it('leaves focus where the replacing screen put it when the opener is gone', async () => {
    function Harness({ showDialog }: { showDialog: boolean }) {
      return showDialog ? (
        <>
          <button type="button">Delete my account</button>
          <ConfirmByTyping {...baseProps} />
        </>
      ) : (
        <button type="button">Your account has been deleted.</button>
      )
    }
    const utils = render(<Harness showDialog />)

    utils.rerender(<Harness showDialog={false} />)
    const note = screen.getByRole('button', {
      name: 'Your account has been deleted.',
    })
    note.focus()

    await waitFor(() => expect(note).toHaveFocus())
    expect(document.activeElement).not.toBe(document.body)
  })

  it('keeps the message region mounted and empty when clean, and refills and refocuses it on every message', async () => {
    const user = userEvent.setup()
    const { rerenderDialog } = renderDialog({ error: null })

    const region = screen.getByTestId('confirm-by-typing-error')
    expect(region).toHaveAttribute('role', 'alert')
    expect(region).toHaveAttribute('tabindex', '-1')
    expect(region).toBeEmptyDOMElement()

    rerenderDialog({
      error:
        "You're the only admin. Make someone else an admin first, then you can leave.",
    })
    expect(region).toHaveTextContent(
      "You're the only admin. Make someone else an admin first, then you can leave.",
    )
    await waitFor(() => expect(region).toHaveFocus())

    await user.type(
      screen.getByTestId('confirm-by-typing-input'),
      expectedValue,
    )
    expect(region).toHaveTextContent(
      "You're the only admin. Make someone else an admin first, then you can leave.",
    )

    rerenderDialog({ error: null })
    expect(region).toBeEmptyDOMElement()
    screen.getByTestId('confirm-by-typing-input').focus()

    rerenderDialog({
      error:
        "You're the only admin. Make someone else an admin first, then you can leave.",
    })
    await waitFor(() => expect(region).toHaveFocus())
  })

  it('leaves every element other than the confirming action live, in every typed state (absent-not-disabled)', async () => {
    const user = userEvent.setup()
    renderDialog({ error: "Couldn't delete your account." })

    for (const typed of ['', 'ana@', expectedValue]) {
      const input = screen.getByTestId('confirm-by-typing-input')
      await user.clear(input)
      if (typed) {
        await user.type(input, typed)
      }

      const scope = within(dialog())
      const interactive = [
        ...scope.queryAllByRole('button'),
        ...scope.queryAllByRole('link'),
        ...scope.queryAllByRole('textbox'),
      ].filter((el) => el !== submit())
      expect(interactive.length).toBeGreaterThan(0)
      for (const el of interactive) {
        expect(el).toBeEnabled()
        expect(el).not.toHaveAttribute('aria-disabled', 'true')
      }
    }
  })

  it('carries no caller-specific wording: a second caller supplies its own labels and address', async () => {
    const user = userEvent.setup()
    const onConfirm = vi.fn(async () => {})
    renderDialog({
      heading: 'Remove ana@northwind.example?',
      body: 'They lose access to this organization straight away.',
      expectedValue: 'ana@northwind.example',
      confirmLabel: 'Remove',
      confirmPendingLabel: 'Removing…',
      onConfirm,
    })

    expect(
      screen.getByRole('dialog', { name: 'Remove ana@northwind.example?' }),
    ).toBeInTheDocument()
    const confirm = screen.getByRole('button', { name: 'Remove' })
    expect(confirm).toBeDisabled()

    await user.type(
      screen.getByTestId('confirm-by-typing-input'),
      'ana@northwind.example',
    )
    await user.click(confirm)

    expect(onConfirm).toHaveBeenCalledTimes(1)
  })
})
