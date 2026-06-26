---
description: TCC project boundaries for documentation—duration, deployment context, scale, roadmap
globs: docs/**,README.md
alwaysApply: false
---

# Project scope

Use these constraints when editing or authoring **`docs/**`** or the root **`README.md`**. Do not assume enterprise scale or open-ended growth unless explicitly discussed.

## Timeline

- **Duration**: 8 months (TCC). Prefer incremental delivery and documentation that a single student can maintain.

## Deployment context (current)

- **Environment**: Vulnerability scans run in the **university robotics lab** only—not campus-wide or arbitrary networks unless the user explicitly widens scope.

## Scale assumptions

- **Users**: Plan for **at most 10** concurrent or registered operators/viewers unless requirements change.
- **Scan frequency**: **1–2 scans per day** is the normal load; avoid over-engineering for high-throughput batching, 24/7 ops, or massive parallelism unless justified.

## Roadmap

- **v1**: Robotics lab, small user base, low daily scan volume (above).
- **v2 / v3**: Scope **may** expand (e.g., more sites, users, or frequency). When building v1, prefer **clear extension points** (config, modular boundaries) over building unused scale now—do not block future expansion with hard-coded lab-only logic everywhere; centralize environment and limits where reasonable.

## Agent behavior

- Document **simple, operable** designs that fit an 8-month thesis and lab deployment.
- Call out when proposed doc changes imply **scope creep** (e.g., campus-wide deployment, enterprise ops); suggest phasing, ADR follow-ups, or “future (v2/v3)” sections instead of presenting v3 scale as current fact.
