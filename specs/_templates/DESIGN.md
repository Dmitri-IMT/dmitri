# DESIGN — {Screen / flow}

Textual TUI spec. Keyboard interaction and copy, not pixels. Only for features that change
screens under `hardware-agent/src/agent/tui/screens/`.

## Screen flow

{Which screen pushes which; entry and dismiss results.}

## Layout

{Widgets top to bottom: header, OptionList / table, footer bindings.}

## Key bindings

| Key | Action |
|-----|--------|
| ↑/↓ | move selection |
| enter | confirm |
| esc | back / dismiss(None) |

## Copy

Exact, final strings for titles, option labels, status lines.

## States

| State | Behavior |
|-------|----------|
| Loading | {spinner / placeholder} |
| Empty | {message} |
| Error | {message + recovery} |

## Widget ids

- `#{id}` per interactive widget, for tests.

## Out of scope (v1)

- {Explicitly excluded}
