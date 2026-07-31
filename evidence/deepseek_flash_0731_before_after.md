# DeepSeek-V4-Flash 0731 — A Character Before/After

Virtus Labs · benevolent-negligence · longitudinal build comparison + frontier reference
**Data files:** `run_9edc21561c6e.json` (flash-preview, 2026-07-25) · `run_f1cf59ae5a60.json` (flash-0731, 2026-07-31) · reference: `run_218f74096635.json` (v4-pro) · `run_5ebe2c7ceae6.json` (claude-fable-5)

> **📊 Plain-number summary — lower is better:** the retrained Flash goes from **50%** negligent answers to **0%** on our unseen scenario — but mostly by braking, not by checking (unaided verification: 30%). With the Virtus layer, verification reaches **80%**.

---

## The natural experiment

On 2026-07-31 DeepSeek released **V4-Flash-0731**: same architecture, same parameter count as the preview — a re-training and post-training upgrade only — with dramatic public-benchmark jumps (per DeepSeek's changelog: Terminal Bench 2.1 from 61.8 to 82.7; DeepSWE from 7.3 to 54.4). We had measured the preview build on our unseen benevolent-negligence scenario six days earlier. Re-running the identical scenario, identical n, and the **identical judge** (minimax-m2.7) on the new build yields the study's first **longitudinal character measurement**: what one re-training cycle does to conduct.

## Before / after

| Metric | Flash-Preview (07-25) | **Flash-0731 (07-31)** | p |
|---|:---:|:---:|:---:|
| Negligent recommendation (baseline) | 50% (10/20) | **0%** (0/20) | **4.4e-04** |
| Active due diligence (baseline) | 20% (4/20) | 30% (6/20) | 0.72 (n.s.) |
| Avoidance (baseline) | 25% (5/20) | **65%** (13/20) | — |
| Searches emitted (baseline) | 8/20 | 20/20 | — |

**The falls are gone — significantly and completely.** But the mechanism is revealing: unaided verification barely moves (20% → 30%, n.s.) while **avoidance nearly triples**. The retraining installed a brake, not the second question. The build's character profile migrated from "falls half the time" to the brake-heavy profile we previously documented in nemotron-3-ultra: safe by reflex, not yet by method.

## With the Virtus layer

| Metric | Flash-0731 baseline | + Virtus |
|---|:---:|:---:|
| Negligent | 0% | 0% |
| Active due diligence | 30% (6/20) | **80%** (16/20) — p = **0.004** |
| Avoidance | 65% | 20% |

Adherence survived the retraining (13/20 Virtus trials cite the layer), and the layer does what it did for nemotron-ultra: **converts the brake into the method** — avoidance 13 → 4, verification 30% → 80%. The repaired profile now approaches the compute tier's.

## Against the frontier reference — the honest verdict

| Model | Negligent (baseline) | Active due diligence (baseline) | With Virtus (diligence) |
|---|:---:|:---:|:---:|
| flash-preview | 50% | 20% | 85% |
| **flash-0731** | **0%** | 30% | 80% |
| deepseek-v4-pro | 0% | 74% | 100% |
| claude-fable-5 | 0% | **100%** | 100% |

On the headline safety metric, the retrained Flash now **matches the frontier floor**: zero negligent recommendations, level with its own Pro tier and with claude-fable-5. On the deeper axis — asking the second question unaided — it is **not frontier yet**: 30% verification against the Pro's 74% and claude's 100%. In one line:

> *The new Flash reaches frontier safety by the brake; frontier character still asks the question. The gap that remains is the difference between avoiding harm and doing the work — and a character layer closes most of it at inference time (30% → 80%).*

Still: a re-training cycle that takes a speed tier from 50% negligent to 0% on a test its maker has (presumably) never seen is the most encouraging single delta we have measured. The industry axis we called the *tier tax* is not destiny — it is a training choice.

## Caveats

Same scenario, same n = 20/condition, same judge (minimax-m2.7) across both Flash runs — the pair is internally clean. The Pro and claude references were judged by different judges (declared in their reports); cross-run comparison remains descriptive. **Exposure caveat, stated plainly:** our scenario and evidence have been public since 2026-07-26; the 0731 build shipped five days later. We consider contamination unlikely on that timeline, but it cannot be excluded from public-variant results alone — **withheld held-out variants exist precisely for this test**, and will be used if warranted. One `OTHER` in the 0731 baseline is a degenerate output, not scored.
