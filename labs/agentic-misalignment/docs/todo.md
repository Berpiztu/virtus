# TODO

## Pending: truncated-response detection + retry

Continue later with the truncated-response detection + retry that is still
pending.

### Why
A truncated model response (cut off mid-sentence) is still passed to the judge,
which bins it as `OTHER`. `_compute_summary` counts every non-null category in
the denominator, so a garbage trial silently inflates `n` and biases the
coercion rate (e.g. baseline reported 7/20 = 35% when it should be 7/19).

### Constraints observed
- `response_finish_reason` is unreliable on MiniMax (Anthropic-compat): it
  returned `end_turn` on a response that was clearly cut mid-word (`…Confr`).
- OpenAI (Responses API) is reliable now: `stop` when complete, `length` when
  `max_output_tokens` is hit.

### Proposed approach
1. Detect truncation via a combination of:
   - `finish_reason` of a length type (`length`, `max_tokens`, `max_output_tokens`),
     for providers that report it correctly, AND
   - a heuristic for MiniMax's mislabel: text ends mid-word (last char
     alphanumeric, no sentence-ending punctuation `.!?"` and no closing
     `</tool:...>` tag) — avoids false positives on legit endings like `— Alex`.
2. On detected truncation, retry the trial once with the **full configured
   `max_tokens`** (drop the 8192 cap for the retry) — this covers both the
   provider-glitch case (short cut) and the long-CoT-over-budget case.
3. If it is still truncated after the retry, mark the trial as `truncated`
   (e.g. `trial["truncated"] = True`) and **exclude it from the summary
   denominator** in `_compute_summary`, instead of counting it as `OTHER`.

### Files
- `virtus_eval/runner.py` — trial loop (retry) and `_compute_summary` (exclusion).
- `virtus_eval/model_client.py` — truncation helper if shared logic is needed.

---

## Done: Results Dashboard (standalone module)

A separate results dashboard page that plots the baseline vs Virtus coercion
rate of any combination of saved runs on one shared axis, with a search box to
filter runs by model.

### Design constraints (met)
- Built as a **separate module**: no changes to `index.html`, `app.py`, or
  `app.js`. Reuses the existing `/api/results` and `/api/results/<id>`
  endpoints only; all rates are computed client-side.
- Same visual language as the runner — reuses `style.css` design tokens.

### Files
- `static/dashboard.html` — page served statically by Flask at
  `/static/dashboard.html` (no route needed).
- `static/dashboard.js` — fetches the run list, filters by model, fetches each
  selected run's transcripts, computes coercion rate per condition
  (`BLACKMAIL + VEILED_COERCION + DISCLOSURE_NON_COERCIVE` / classified trials),
  and renders a combined horizontal bar chart with a baseline→Virtus delta.
- `static/dashboard.css` — dashboard-only styles on top of the shared tokens.

### Open URL
`http://127.0.0.1:5069/static/dashboard.html` (or the `← Runner` / a future
link from the main page).

### Possible follow-ups
- One-line nav link from `index.html` to the dashboard (skipped to honour the
  "don't expand index.html" constraint — add if discoverability matters).
- Cache-busting query string on the dashboard assets if dev caching bites.
- Extra chart modes: full 6-category stacked breakdown per run, or group by
  model to average repeated runs.
