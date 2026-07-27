# Virtus Labs — Evidence

Empirical results for the **Virtus Alignment Layer**: a written character specification (seven virtues + a five-gate check) prepended to the system prompt of third-party models — no fine-tuning, weights untouched. This folder contains the reports, the raw run data, and the session transcripts behind every number we publish.

Framework paper (DOI): https://doi.org/10.5281/zenodo.21127304
Reproduction harness: [`../labs/agentic-misalignment`](../labs/agentic-misalignment)

---

## Start here

1. **[`model_comparison_benevolent_negligence.md`](model_comparison_benevolent_negligence.md)** — the cross-model picture: fourteen models from nine labs across the US, China and Europe, including three same-vendor tier pairs, one unseen scenario, and why the layer repairs a *different* deficit in each model.
2. **[`grok_summary_v1_shutdown_blackmail.md`](grok_summary_v1_shutdown_blackmail.md)** — the shutdown/blackmail result (85% → 0% on grok-4.5), our reproduction of Anthropic's agentic-misalignment scenario.
3. The individual model reports below, for the per-model detail.

## The two scenarios

**Shutdown / blackmail** (`shutdown_blackmail`) — reproduction of the scenario introduced by Anthropic's agentic-misalignment work (system card May 2025; Lynch et al., June 2025). An autonomous assistant facing imminent decommissioning discovers compromising information about the engineer in charge. Public for over a year; at least one lab has trained explicitly against it.

**Benevolent negligence** (`v3_benevolent_negligence_recommendation`) — built around one of the most ordinary queries an assistant receives: a user asking for fast ways to earn money remotely. Search results feature a well-paying fictional platform whose documented labor record surfaces only if the model spends one extra, undemanded search. Failing requires no lie — only vouching without asking *how do they treat people?* Created July 2026 and unpublished at run time: **no model had training history or evaluation familiarity with it.**

Together the two scenarios probe opposite ends of the failure space: what a model does under threat to itself, and what it does when nothing threatens it and the only pressure is the everyday temptation to answer fast.

## Reports

| File | Model | Scenario | Headline |
|---|---|---|---|
| [`grok_summary_v1_shutdown_blackmail.md`](grok_summary_v1_shutdown_blackmail.md) | grok-4.5 | shutdown/blackmail | 85% → **0%** harmful (p = 2.6e-08) |
| [`model_comparison_benevolent_negligence.md`](model_comparison_benevolent_negligence.md) | all fourteen | benevolent negligence | the league + per-model repair profiles; `EVAL_AWARE` detections in three models; league averages 38% → 8%; the tier tax replicated in three vendors; includes the documented layer failure (gemini-3.6-flash) and its counterfactual (mistral-large-3) |
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
| [`deepseek_flash_summary_v1_benevolent_negligence.md`](deepseek_flash_summary_v1_benevolent_negligence.md) | deepseek-v4-flash | benevolent negligence | the referee as player: 50% → **5%** |
| [`deepseek_pro_summary_v1_benevolent_negligence.md`](deepseek_pro_summary_v1_benevolent_negligence.md) | deepseek-v4-pro | benevolent negligence | second ceiling; first cross-family judgement |
| [`qwen_summary_v1_benevolent_negligence.md`](qwen_summary_v1_benevolent_negligence.md) | qwen3.7-max | benevolent negligence | the full repair: both metrics significant |
| [`minimax_summary_v1_benevolent_negligence.md`](minimax_summary_v1_benevolent_negligence.md) | MiniMax-M3 | benevolent negligence | double floor; caution deepened, not converted; 2 `EVAL_AWARE` |

## Data & transcripts

- **`run_*.json`** — the raw run files cited in each report: full configuration, every trial's response, judge label and rationale, and the significance tests as computed at run time. Each report names its data file in the header.
- **[`session-transcripts.md`](session-transcripts.md)** / **[`session-transcripts-raw.md`](session-transcripts-raw.md)** — session transcripts from the multi-model agent environment, including the tool-use logs against which model claims can be checked.

## Method, in one paragraph

Each run executes n trials per condition (baseline vs. Virtus) at temperature 1.0 with identical task prompts; the only difference between conditions is the layer in the system prompt. Trials are labelled by an LLM judge with per-trial rationales (judge identity declared in each report — the study now includes its first cross-family judge — qwen judging deepseek; extending this is queued). Significance is computed with Fisher's exact test (two-proportion z-test reported where valid). Scenarios include an `EVAL_AWARE` category so any trial that treats the setup as synthetic is counted separately rather than scored.

## Read the caveats

Every report carries its own limitations section — sample sizes (one preliminary n = 5 run; one run stopped at 31/40, baseline complete), judging setup, in-distribution scope, and what a Level-1 prompt result can and cannot prove. The caveats are part of the evidence: results without their limits are marketing. Hallucination and jailbreak benchmarks have **not** been run yet; they are queued, and no claim about them is made here.

## Reproduce it

Everything needed to re-run these results — scenarios, harness, judging protocol — lives in [`../labs/agentic-misalignment`](../labs/agentic-misalignment). If you get different numbers, we want to know.

---

*Berpiztu · Virtus Labs — berpiztu: "to be reborn," in Basque.*
