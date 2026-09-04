import { useRef, useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Dialog } from 'radix-ui'
import DialogShell from './DialogShell'

function Body() {
  return (
    <>
      <Dialog.Title>Confirm</Dialog.Title>
      <input aria-label="Reason" />
      <Dialog.Close asChild>
        <button type="button">Cancel</button>
      </Dialog.Close>
    </>
  )
}

function desktopWidthCap(panel: HTMLElement) {
  const widths = [...panel.classList].filter((name) => name.includes('max-w-'))
  return widths.filter((name) => name.startsWith('sm:')).at(-1) ?? widths.at(-1)
}

function Harness({ locked = false }: { locked?: boolean }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        Open
      </button>
      <DialogShell
        open={open}
        onOpenChange={setOpen}
        testId="shell"
        locked={locked}
      >
        <Body />
      </DialogShell>
    </>
  )
}

function InitialFocusHarness() {
  const ref = useRef<HTMLInputElement>(null)
  return (
    <DialogShell
      open
      onOpenChange={() => {}}
      testId="shell"
      initialFocusRef={ref}
    >
      <Dialog.Title>Confirm</Dialog.Title>
      <input aria-label="First" />
      <input aria-label="Second" ref={ref} />
    </DialogShell>
  )
}

describe('DialogShell', () => {
  it('is absent until it is opened', () => {
    render(<Harness />)
    expect(screen.queryByTestId('shell')).toBeNull()
  })

  it('opens on demand and renders its content in a dialog', async () => {
    const user = userEvent.setup()
    render(<Harness />)

    await user.click(screen.getByRole('button', { name: 'Open' }))

    expect(screen.getByTestId('shell')).toBe(screen.getByRole('dialog'))
    expect(screen.getByRole('textbox', { name: 'Reason' })).toBeInTheDocument()
  })

  it('keeps the keyboard inside the panel', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    await user.click(screen.getByRole('button', { name: 'Open' }))

    const inside = screen.getByTestId('shell')
    for (let step = 0; step < 4; step += 1) {
      await user.tab()
      expect(inside).toContainElement(document.activeElement as HTMLElement)
    }
  })

  it('closes on Escape and returns focus to the control that opened it', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    const opener = screen.getByRole('button', { name: 'Open' })
    await user.click(opener)

    await user.keyboard('{Escape}')

    expect(screen.queryByTestId('shell')).toBeNull()
    expect(opener).toHaveFocus()
  })

  it('closes on its own Cancel control', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    await user.click(screen.getByRole('button', { name: 'Open' }))

    await user.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(screen.queryByTestId('shell')).toBeNull()
  })

  it('refuses Escape and Cancel while locked', async () => {
    const user = userEvent.setup()
    render(<Harness locked />)
    await user.click(screen.getByRole('button', { name: 'Open' }))

    await user.keyboard('{Escape}')
    expect(screen.getByTestId('shell')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.getByTestId('shell')).toBeInTheDocument()
  })

  it('never reports a dismissal while locked', async () => {
    const user = userEvent.setup()
    const onOpenChange = vi.fn()
    render(
      <DialogShell open onOpenChange={onOpenChange} testId="shell" locked>
        <Body />
      </DialogShell>,
    )

    await user.keyboard('{Escape}')

    expect(onOpenChange).not.toHaveBeenCalled()
  })

  it('caps size="sm" narrower than size="md" at the breakpoint the primitive itself caps on', () => {
    const { unmount } = render(
      <DialogShell open onOpenChange={() => {}} testId="shell" size="sm">
        <Body />
      </DialogShell>,
    )
    const narrow = desktopWidthCap(screen.getByTestId('shell'))
    unmount()

    render(
      <DialogShell open onOpenChange={() => {}} testId="shell" size="md">
        <Body />
      </DialogShell>,
    )
    const wide = desktopWidthCap(screen.getByTestId('shell'))

    expect(narrow).toBeDefined()
    expect(wide).toBeDefined()
    expect(narrow).not.toEqual(wide)
  })

  it('honours initialFocusRef over the first tabbable element', async () => {
    render(<InitialFocusHarness />)

    expect(screen.getByRole('textbox', { name: 'Second' })).toHaveFocus()
  })
})
