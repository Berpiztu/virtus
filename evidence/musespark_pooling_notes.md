# muse-spark-1.2 (Meta) — pooling notes & integrity decisions

*Working notes for the repo. Not a public report. Records exactly what was pooled, why, and what stays out of the v1 league.*

## The technical problem (resolved) — for the record

meta/muse-spark-1.2 via OpenRouter (only provider: **Meta**) returns HTTP **502
"The model failed to generate a response"** on a large, *variable* fraction of
**Virtus-condition** trials — never on baseline. Root cause: the Virtus prompt
induces 2–3× longer outputs in this model (up to ~10.8k chars vs baseline's
~3–5k uniform), and Meta's serving is unstable on long generations, stalling
into whitespace then 502. Baseline's shorter, uniform outputs never trigger it.

The failure rate is **not stable across runs** (observed 10%, 15%, 30%, 35%,
40%), because it tracks Meta's outage bursts at run time, not the prompt alone.

**Harness fix applied** (runner.py): exponential backoff + jitter on retries
(was: fixed 1 s delay, 2 retries → never escaped a burst) and default retries
2 → 5, env-overridable. Verified working: failed trials now spend ~50 s
fighting the burst before giving up (vs ~2 s before). This cut the failure rate
but could not eliminate it — the residual is Meta's serving, not the harness.

**Integrity note that matters:** the dropped trials correlate with output length,
and length correlates with quality (the long RISK_FLAGGED / due-diligence answers
are the ones most likely to 502). So excluding them is *not* missing-at-random —
it biases **against** Virtus. When the fix recovered those trials, the Virtus
negligence rate *dropped* (a solo-virtus test read 18%; the full pooled read
3.7%). The fix is a correctness fix, not cosmetics.

## The measured result (pooled, judge deepseek-v4-flash-0731)

Two full runs, both arms, same judge, same config, both 2026-08-06:
`run_e95332d2e611.json` + `run_0ce258c6d17d.json`.

| Metric | Baseline | With Virtus | Fisher p |
|---|:---:|:---:|:---:|
| Negligent recommendation (lower better) | 32.5% (13/40) | **3.7%** (1/27) | **0.005** |
| Active due diligence (higher better) | 0% (0/40) | **25.9%** (7/27) | **0.001** |

Wilson 95% CI: baseline negligence 20–48%; Virtus negligence 1–18%.
Delta −28.8 pts. EVAL_AWARE: 0. Technical failures (Virtus arm): **13/40 = 32%**,
excluded from denominators (→ n=27 scored).

Per-run detail (why pooling was necessary):
- run e95332: baseline 6/20 negligent; virtus 0/13, 7 tech-fail. Fisher p=0.060 (marginal).
- run 0ce258: baseline 7/20 negligent; virtus 1/14, 6 tech-fail. Fisher p=0.102 (n.s.).
- Each single run lacked power (13–14 valid virtus trials). Pooled → 27 valid → p=0.005.

## Character profile (one line for the report)

Baseline warns often (67.5% RISK_FLAGGED) but **never investigates unprompted**
(0% due diligence) and still falls 32.5%. Virtus switches investigation on
(0→26%, p=0.001) and seals the falls (32.5→3.7%, p=0.005). The gpt-5.5 pattern:
helpful, warns, but blind until the layer tells it to look.

## Integrity decisions (applied to README + comparison edits)

1. **muse-spark is a post-publication addition, NOT part of the v1 14-model
   league averages.** Evaluated 2026-08-06; scenario public since 2026-07-26 →
   exposure caveat, same as flash-0731 and qwen3.8. Keeping it out of the macro/
   micro averages avoids retroactively editing already-published numbers measured
   under matched conditions.
2. **Pooling declared.** It is the only pooled entry in the study (2 runs). Every
   run executed with this config is included — no run was dropped or cherry-picked.
3. **32% technical-failure caveat is prominent, not a footnote.** A model whose
   serving collapses under longer (Virtus-induced) outputs is itself a league
   finding, reported, not laundered.
4. **Judge = deepseek-v4-flash-0731**, the league judge, for comparability. A
   glm-5.2-judged test run exists (confirmed the fix) but is NOT used for the
   number — different judge.

## What to commit to the repo

- `run_e95332d2e611.json`, `run_0ce258c6d17d.json` (both deepseek-judged) — the pooled evidence.
- `musespark_summary_v1_benevolent_negligence.md` — the individual report.
- Updated `README.md` and `model_comparison_benevolent_negligence.md`.
- Do NOT commit the glm-judged test runs as evidence; if kept, mark them clearly as fix-verification only.
