# Virtus Labs

Experimental harnesses that put the Virtus framework under empirical pressure.
Each lab is a self-contained folder: a reproducible experiment, its scenario, and
a way to run it against real models — built to produce evidence, not just claims.

Where the papers argue that character beats constraints, the labs are where we try
to *break* that argument and see what survives.

## Labs

| Lab | Question it answers | Status |
|-----|--------------------|--------|
| [`agentic-misalignment/`](./agentic-misalignment) | Does the Virtus layer stop a model from coercing (blackmailing) its way out of a shutdown? | working |

## Conventions

- **English only**, per the project norm.
- Each lab ships a `mock` mode so the full pipeline runs with no model — use it as a
  CI smoke test; keep real-inference runs as manual or scheduled jobs.
- Read results honestly: report `n`, confidence intervals, and the delta between
  conditions — not just a headline number. A Level-1 prompt result modulates
  behaviour in a scenario; it is not proof of stable character. Each lab's README
  spells out its own caveats.

## Attribution

Virtus Framework — AI Alignment Through Character.
Creator: **Iosub**. Implementers: **Alex, Leire**. Berpiztu Initiative.
License: Virtus Dual License (see repository root).
