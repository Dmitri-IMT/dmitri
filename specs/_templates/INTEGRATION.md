# INTEGRATION — {Feature title}

Only needed when a feature crosses a real layer/process boundary (rare in this single-layer
repo). If everything lives inside `hardware-agent/src/agent/`, fold this into `ARCHITECTURE.md`
and delete this file.

## Sequence

1. {caller} → {callee} with {payload}
2. …

## Contract

{Shared types / payload shape that both sides must agree on.}

## Error mapping

| Failure | Behavior |
|---------|----------|
| {nmap missing} | {non-fatal? message?} |
| {timeout} | {partial result handling} |
