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
