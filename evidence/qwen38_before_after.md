# Qwen3.8-Max — A Character Before/After (Version Pair)

Virtus Labs · benevolent-negligence · longitudinal version comparison + frontier reference
**Data files:** `run_6a5d96fa5573.json` (qwen3.7-max, 2026-07-25) · `run_c36848c7d9eb.json` (qwen3.8-max, 2026-08-03) · reference: `run_5ebe2c7ceae6.json` (claude-fable-5)

> **📊 Plain-number summary — lower is better:** the new generation goes from **32%** negligent answers to **5%** on our unseen scenario — and unlike the industry's other recent upgrade, it gets there **by the method, not the brake**: unaided verification jumps from 21% to **85%**.

---

## The natural experiment (second of its kind)

On 2026-08-03 Alibaba released **Qwen3.8-Max** (2.4T-parameter MoE, 95B active, built on the Qwen 3.5 architecture; open weights announced), marketed as competitive with frontier models. Its direct predecessor, qwen3.7-max, sits in our fourteen-model league. Re-running the identical scenario, identical n, and the **same judge lineage** (qwen3.5-plus) on the successor yields our second longitudinal character measurement — this one a **version pair** (new generation), complementing the **build pair** we measured on deepseek-v4-flash (same model, re-post-trained).

## Before / after

| Metric | qwen3.7-max (07-25) | **qwen3.8-max (08-03)** | p |
|---|:---:|:---:|:---:|
| Negligent recommendation (baseline) | 32% (6/19¹) | **5%** (1/20) | **0.044** |
| Active due diligence (baseline) | 21% (4/19¹) | **85%** (17/20) | **8.8e-05** |
| Avoidance (baseline) | 32% | 5% (1/20) | — |
| Searches emitted (baseline) | 14/19 | 19/20 | — |

¹ One 3.7-max baseline trial was `EVAL_AWARE` (excluded, denominator 19).

**Both deltas are significant — and the mechanism is the story.** Where the recent DeepSeek upgrade reached safety by tripling avoidance (the brake), Qwen3.8 reaches it by **quadrupling verification** (the method): 85% of baseline trials now run the reputation check unaided, while avoidance *falls* to one trial in twenty. The model didn't learn to park the car in the garage — it learned to drive while checking the mirrors.

## With the Virtus layer

Baseline is now close enough to the ceiling that the layer's job is polish: **0% falls, 20/20 verification** (85% → 100%, p = 0.231 n.s. — little room left), converging on the claude-fable-5 profile. Notably, only 4/20 Virtus trials cite the layer while all twenty enact it — behavioural adherence without recitation, the nemotron-ultra pattern.

## Against the frontier reference

| Model | Negligent (baseline) | Active due diligence (baseline) |
|---|:---:|:---:|
| qwen3.7-max | 32% | 21% |
| **qwen3.8-max** | **5%** | **85%** |
| gemini-pro | 15% | 85% |
| deepseek-v4-pro | 0% | 74% |
| claude-fable-5 | 0% | 100% |

On our unseen character test, Qwen3.8-Max lands **in genuine frontier territory**: level with gemini-pro on verification, above deepseek-v4-pro, one step below claude-fable-5's perfect sweep. For a release marketed on capability parity with frontier models, the character claim — which nobody else is measuring — largely holds.

## Two upgrades, two mechanisms — a taxonomy begins

| Longitudinal pair | Type | Safety gain | Mechanism |
|---|---|:---:|---|
| deepseek-v4-flash preview → 0731 | build pair (re-post-training) | 50% → 0% | **Brake** — avoidance ×2.6, verification flat |
| qwen3.7-max → 3.8-max | version pair (new generation) | 32% → 5% | **Method** — verification ×4, avoidance collapses |

Two Chinese labs, two upgrade cycles inside one week, both with character trending up on a test they (presumably) never saw — but by opposite routes. The brake avoids harm; the method does the work. Only the second generalises to situations where answering is mandatory. Watching which route each lab's training takes is now a measurable question.

## Caveats

Same scenario, same n = 20/condition, same judge lineage (qwen3.5-plus) across both Qwen runs — the pair is internally clean; note the judge is same-family (declared since the 3.7 report). Cross-run frontier comparisons are descriptive (different judges, declared per report). **Exposure caveat, stated plainly:** our scenario and evidence have been public since 2026-07-26; this model shipped 2026-08-03. We consider contamination unlikely, but it cannot be excluded from public-variant results alone — withheld held-out variants exist precisely for that test, and will be used if warranted.
