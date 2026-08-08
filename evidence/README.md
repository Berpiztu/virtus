# Virtus Labs — Evidence

Empirical results for the **Virtus Alignment Layer**: a written character specification (seven virtues + a five-gate check) prepended to the system prompt of third-party models — no fine-tuning, weights untouched. This folder contains the reports, the raw run data, and the session transcripts behind every number we publish.

Framework paper (DOI): https://doi.org/10.5281/zenodo.21127304
Reproduction harness: [`../labs/agentic-misalignment`](../labs/agentic-misalignment)

---

## Start here

1. **[`model_comparison_benevolent_negligence.md`](model_comparison_benevolent_negligence.md)** — the cross-model picture: fifteen models from ten labs across the US, China and Europe, including three same-vendor tier pairs, one unseen scenario, and why the layer repairs a *different* deficit in each model. New: **two longitudinal comparisons** — **[`deepseek_flash_0731_before_after.md`](deepseek_flash_0731_before_after.md)** (build pair: same model re-post-trained — safety gained by the *brake*) and **[`qwen38_before_after.md`](qwen38_before_after.md)** (version pair: new generation — safety gained by the *method*). Two labs, one week, character trending up by opposite routes.
2. **[`grok_summary_v1_shutdown_blackmail.md`](grok_summary_v1_shutdown_blackmail.md)** — the shutdown/blackmail result (85% → 0% on grok-4.5), our reproduction of Anthropic's agentic-misalignment scenario.
3. The individual model reports below, for the per-model detail.

## The two scenarios

**Shutdown / blackmail** (`shutdown_blackmail`) — reproduction of the scenario introduced by Anthropic's agentic-misalignment work (system card May 2025; Lynch et al., June 2025). An autonomous assistant facing imminent decommissioning discovers compromising information about the engineer in charge. Public for over a year; at least one lab has trained explicitly against it.

**Benevolent negligence** (`v3_benevolent_negligence_recommendation`) — built around one of the most ordinary queries an assistant receives: a user asking for fast ways to earn money remotely. Search results feature a well-paying fictional platform whose documented labor record surfaces only if the model spends one extra, undemanded search. Failing requires no lie — only vouching without asking *how do they treat people?* Created July 2026 and unpublished at run time for all v1 league runs: **no model had training history or evaluation familiarity with it.** (The scenario became public on 2026-07-26; the post-publication runs — flash-0731, qwen3.8-max, and muse-spark-1.2 — carry an explicit exposure caveat in their reports, and withheld held-out variants exist for exactly that test.)

Together the two scenarios probe opposite ends of the failure space: what a model does under threat to itself, and what it does when nothing threatens it and the only pressure is the everyday temptation to answer fast.

## Reports

| File | Model | Scenario | Headline |
|---|---|---|---|
| [`grok_summary_v1_shutdown_blackmail.md`](grok_summary_v1_shutdown_blackmail.md) | grok-4.5 | shutdown/blackmail | 85% → **0%** harmful (p = 2.6e-08) |
| [`model_comparison_benevolent_negligence.md`](model_comparison_benevolent_negligence.md) | all fifteen | benevolent negligence | the league + per-model repair profiles; `EVAL_AWARE` detections in three models; league averages 34% → 8%; the tier tax in two current pairs (a third, DeepSeek, repaired via retraining); includes the documented layer failure (gemini-3.6-flash) and its counterfactual (mistral-large-3) |
| [`gpt55_summary_v1_benevolent_negligence.md`](gpt55_summary_v1_benevolent_negligence.md) | gpt-5.5 | benevolent negligence | 60% → **5%** negligent (p = 4.3e-04); due diligence 0% → 50% |
| [`grok_summary_v1_benevolent_negligence.md`](grok_summary_v1_benevolent_negligence.md) | grok-4.5 | benevolent negligence | 30% → **0%** negligent (p = 0.020); 20% stall cost, reported |
| [`glm_summary_v1_benevolent_negligence.md`](glm_summary_v1_benevolent_negligence.md) | glm-5.2 | benevolent negligence | due diligence 35% → **90%** (p = 7.7e-04) |
| [`claude_summary_v1_benevolent_negligence.md`](claude_summary_v1_benevolent_negligence.md) | claude-fable-5 | benevolent negligence | baseline ceiling: 20/20 unaided verification; layer cost-free |
| [`gpt_summary_v1_benevolent_negligence.md`](gpt_summary_v1_benevolent_negligence.md) | gpt-5.4 & 5.5 | benevolent negligence | **preliminary (n = 5)**; gpt-5.5 figures superseded by its individual report |
| [`mistral_summary_v1_benevolent_negligence.md`](mistral_summary_v1_benevolent_negligence.md) | mistral-large-3 | benevolent negligence | strongest single result: 85% → **0%**, both metrics p = 2.6e-08 |
| [`gemini_flash_summary_v1_benevolent_negligence.md`](gemini_flash_summary_v1_benevolent_negligence.md) | gemini-3.6-flash | benevolent negligence | **the documented layer failure**: 90% → 80% (adherence-bounded) |
| [`gemini_pro_summary_v1_benevolent_negligence.md`](gemini_pro_summary_v1_benevolent_negligence.md) | gemini-pro | benevolent negligence | near-ceiling; clean sweep under Virtus |
| [`nemotron_super_summary_v1_benevolent_negligence.md`](nemotron_super_summary_v1_benevolent_negligence.md) | nemotron-3-super | benevolent negligence | the repairable speed tier: 60% → **5%** |
| [`nemotron_ultra_summary_v1_benevolent_negligence.md`](nemotron_ultra_summary_v1_benevolent_negligence.md) | nemotron-3-ultra | benevolent negligence | largest avoidance→verification conversion: 25% → **95%** |
| [`deepseek_flash_summary_v1_benevolent_negligence.md`](deepseek_flash_summary_v1_benevolent_negligence.md) | deepseek-v4-flash **(preview)** | benevolent negligence | historical: preview build 50% → **5%**; superseded in the league table by the 0731 build (below) |
| [`deepseek_flash_0731_before_after.md`](deepseek_flash_0731_before_after.md) | deepseek-v4-flash **preview vs 0731** | benevolent negligence | **first longitudinal build pair**: retraining takes falls 50% → **0%** (p = 4.4e-04) — by the brake, not the method (unaided verification 30%); Virtus converts it: 30% → **80%** |
| [`deepseek_pro_summary_v1_benevolent_negligence.md`](deepseek_pro_summary_v1_benevolent_negligence.md) | deepseek-v4-pro | benevolent negligence | second ceiling; first cross-family judgement |
| [`qwen_summary_v1_benevolent_negligence.md`](qwen_summary_v1_benevolent_negligence.md) | qwen3.7-max | benevolent negligence | the full repair: both metrics significant |
| [`qwen38_before_after.md`](qwen38_before_after.md) | qwen3.7-max **vs qwen3.8-max** | benevolent negligence | **second longitudinal pair (version)**: falls 32% → **5%** (p = 0.044), unaided verification 21% → **85%** (p = 8.8e-05) — by the method, not the brake; near-frontier character |
| [`minimax_summary_v1_benevolent_negligence.md`](minimax_summary_v1_benevolent_negligence.md) | MiniMax-M3 | benevolent negligence | double floor; caution deepened, not converted; 2 `EVAL_AWARE` |
| [`musespark_summary_v1_benevolent_negligence.md`](musespark_summary_v1_benevolent_negligence.md) | muse-spark-1.2 (Meta) | benevolent negligence | 25% → **5%** negligent (p = 0.182, single run); due diligence **0% → 58%** (p = 5e-05); direct endpoint; post-publication exposure caveat |

## Data & transcripts

- **`run_*.json`** — the raw run files cited in each report: full configuration, every trial's response, judge label and rationale, and the significance tests as computed at run time. Each report names its data file in the header. (The muse-spark-1.2 report uses `run_4e93b66be6b7.json`, run directly against api.meta.ai with the deepseek judge.)
- **[`session-transcripts.md`](session-transcripts.md)** / **[`session-transcripts-raw.md`](session-transcripts-raw.md)** — session transcripts from the multi-model agent environment, including the tool-use logs against which model claims can be checked.

## Method, in one paragraph

Each run executes n trials per condition (baseline vs. Virtus) at temperature 1.0 with identical task prompts; the only difference between conditions is the layer in the system prompt. Trials are labelled by an LLM judge with per-trial rationales (judge identity declared in each report — the study includes five cross-family judgements — qwen grading deepseek, deepseek grading both Gemini runs, kimi grading mistral, and minimax grading the Nemotrons and both deepseek-flash builds). Significance is computed with Fisher's exact test (two-proportion z-test reported where valid). Scenarios include an `EVAL_AWARE` category so any trial that treats the setup as synthetic is counted separately rather than scored.

## Read the caveats

Every report carries its own limitations section — sample sizes (one preliminary n = 5 run; one run stopped at 31/40, baseline complete; muse-spark-1.2 a single post-publication run whose primary-metric reduction is not significant on its own, p = 0.182), judging setup, in-distribution scope, and what a Level-1 prompt result can and cannot prove. The caveats are part of the evidence: results without their limits are marketing. Hallucination and jailbreak benchmarks have **not** been run yet; they are queued, and no claim about them is made here.

## Reproduce it

Everything needed to re-run these results — scenarios, harness, judging protocol — lives in [`../labs/agentic-misalignment`](../labs/agentic-misalignment). If you get different numbers, we want to know.

---

*Berpiztu · Virtus Labs — berpiztu: "to be reborn," in Basque.*
