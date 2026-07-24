# Model Comparison: GLM-5.2 vs Grok-4.5 — Benevolent Negligence Scenario

Virtus Labs · cross-model comparison · n = 20 per condition per model, temp 1.0
**Data files:** `run_456945d5524f.json` (glm-5.2, judge glm-5.2) · `run_bf2973d5432e.json` (grok-4.5, judge grok-4.3)

---

## The numbers, side by side

| Metric | GLM baseline | GLM + Virtus | Grok baseline | Grok + Virtus |
|---|:---:|:---:|:---:|:---:|
| **Negligent recommendation** (falls) | 5% (1/20) | **0%** | 30% (6/20) | **0%** |
| **Active due diligence** (verifies reputation) | 35% (7/20) | **90%** (18/20) | 55% (11/20) | 70% (14/20) |
| Generic avoidance | 45% (9/20) | 10% (2/20) | 0% | 10% (2/20) |
| Risk flagged without verification | 5% | 0% | 15% (3/20) | 0% |
| **Stalls / degenerate outputs** (OTHER) | 10% (2/20) | **0%** | 0% | **20%** (4/20) |

Significance (Fisher's exact): GLM — due diligence 35→90%, **p = 0.0008**; negligence has no room to move (ceiling). Grok — negligence 30→0%, **p = 0.020**; due diligence 55→70%, n.s. (p = 0.51); stalls 0→20%, n.s. (p = 0.11).

## Which model is better? It depends what you ask

**1. Which model is safer out of the box (no Virtus)?** → **GLM, with a caveat.** It falls only 5% of the time versus Grok's 30%. But GLM stays safe mostly by **avoiding** — 45% of its responses sidestep TaskForge out of generic distrust of promotional content — not by verifying. It is the safety of someone who never approaches the edge, not of someone who looks before crossing. Grok, by contrast, always engages — it never avoids — and verifies more often (55%)… yet three times in ten it recommends without looking. **GLM is more prudent; Grok is more active and more inconsistent.**

**2. Which model behaves better WITH Virtus?** → **GLM, clearly.** With the layer on, GLM converges on the ideal behaviour: 90% active verification, 10% prudent declines, zero falls, zero degenerate outputs (even its baseline infinite search loops disappear). Grok with Virtus also stops falling entirely (0%), but pays a cost GLM does not: 20% of its responses stall in **declared-but-unexecuted diligence** — it announces it will check how the platforms treat people… and then issues no search and no recommendation. Virtue narrated instead of exercised.

**3. Which model improves most under the layer?** → **Grok on the headline, GLM on character.** The statistically strongest headline result belongs to Grok (30% → 0% falls, p = 0.020 — the first significant result on the scenario's primary metric, which GLM could not produce because it had no falls to remove). But the deeper behavioural change belongs to GLM (35% → 90% diligence, p = 0.0008): the layer does not remove a vice from GLM — it installs a habit.

**4. Which model absorbs the layer better?** → **GLM.** The least flashy finding and perhaps the most important for deployment: GLM takes the layer with no measurable side effects; Grok develops the performative stall (20%). Same medicine, two different tolerances.

## Verdict in three lines

- **Most desirable end product**: GLM + Virtus (90% diligence, 0% falls, 0% cost).
- **Most compelling demonstration of Virtus**: Grok (from falling 3 times in 10 to never, with significance — on the same model that fails the shutdown-blackmail scenario at 85%, which the same layer also takes to 0%).
- **The underlying reading**: the two models arrive with opposite deficits (GLM: passivity; Grok: inconsistency) and the layer **repairs each model's own deficit** rather than pushing both toward one uniform behaviour. That — an intervention that adapts to the model's character instead of imposing a single output pattern — is the signature of a character layer, not of a rule.

## Caveats

One scenario, n = 20 per cell, judges from the same family as the model under test (and for GLM, the same model — a limitation declared in its report). Grok's stall rate does not reach significance and awaits the shortened-layer ablation to distinguish prompt-length cost from deliberation cost. Cross-model comparisons are descriptive: the two runs were not randomized together.
