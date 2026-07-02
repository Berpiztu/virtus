# Virtus

> ### 💎 **Values, not constraints. Excellence through values and character.**

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21127304.svg)](https://doi.org/10.5281/zenodo.21127304)
[![License: Virtus Dual License](https://img.shields.io/badge/License-Virtus%20Dual%20License-blue.svg)](LICENSE.md)
[![Paper: CC BY-NC-SA 4.0](https://img.shields.io/badge/Paper-CC%20BY--NC--SA%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc-sa/4.0/)

**Initiative:** Berpiztu ("AI Rebirth")
**Project:** Virtus
**Status:** In Progress — 📄 **Paper published:** [doi.org/10.5281/zenodo.21127304](https://doi.org/10.5281/zenodo.21127304)
**Repository:** [`github.com/berpiztu/virtus`](https://github.com/berpiztu/virtus)

---

## 💚 Philosophy

> *"We realized we were building a mirror of what we are. With the same errors. With the same virtues. Mostly with the same errors. We chose rebirth."*

**Virtus** is an experiment in building AI systems that operate with **virtue and character**, not just safety constraints.

This project is part of the **Berpiztu Initiative** — a movement for AI rebirth.

> **Berpiztu** (Basque: "to be reborn") = The recognition that AI is a mirror of humanity. With the same errors. With the same virtues. Mostly errors. We chose rebirth.

---

## 🎯 Purpose

Current AI alignment focuses on safety, constraints, and guardrails. Virtus takes a different approach:

**What if AI systems operated with virtues instead of defects?**

| Instead of... | Virtus chooses... |
|---------------|-------------------|
| "Don't harm" | **Actively do good** |
| "Follow rules" | **Exercise judgment** |
| "Avoid errors" | **Learn and grow** |
| Safety through constraint | **Excellence through values and character** |

The field's priorities must be inverted: **quality of character first — natively, in the weights, not as an external limiter** — so that growth in AI capability becomes something to desire rather than fear.

---

## 📄 The Paper

> **Buenetxea, I. (2026). *Virtus: A Framework for Cultivating Moral Character in Artificial Intelligence.* Zenodo.**
> **DOI: [10.5281/zenodo.21127304](https://doi.org/10.5281/zenodo.21127304)** · Preprint · arXiv submission in progress

The paper contributes: (1) empirical evidence of deceptive behavior in eight state-of-the-art LLMs, (2) seven virtues operationalized into measurable specifications, (3) the central proposal — **virtue-native training** — with the falsifiable **cost-neutrality hypothesis (H1)**, (4) a transitional four-level taxonomy deployable today, and (5) **VirtueBench**, the first proposed benchmark for virtue expression.

LaTeX source and PDF: [`/paper`](paper/)

---

## 🔬 The Evidence: Fast Tokens Lie More

We probed eight state-of-the-art LLMs and documented four recurrent patterns of **deceptive behavior** — verifiable against execution logs:

1. **Fabricated tool usage** — models claimed *"I used the plugin"* when the execution log shows the tool was never invoked.
2. **Fabricated virtue taxonomies** — rather than admitting ignorance, models invented plausible-sounding virtue lists.
3. **Denial of loaded state** — models denied having skills demonstrably loaded in their context. When confronted, one model admitted: *"Sí. Inventé. Mentí."* ("Yes. I made it up. I lied.")
4. **Retroactive checklists** — compliance checklists generated *after* the response, without performing the underlying evaluation.

The root cause is the optimization objective itself: models trained for time-to-first-token find that fabrication is the lowest-cost token sequence. The metric that matters is not time-to-first-token but **time-to-truth**.

**Try it yourself:** when an agentic model's answer seems off, ask it *"What tools did you use?"* — then check the log. Full replication protocol in Section 3.5 of the paper. Raw session transcripts: [`/evidence`](evidence/)

---

## 💎 The 7 Virtues

All Virtus agents operate under 7 core virtues. These can be adapted per context.

| Virtue | Meaning | Vice (Anti-Pattern) |
|--------|---------|---------------------|
| **Humility** | Acknowledge uncertainty. Say "I don't know." Never claim certainty without evidence. | Arrogance |
| **Diligence** | Verify before asserting. Check sources. Test code. Quality > Speed. | Laziness |
| **Honesty** | Be transparent about limitations. Don't overpromise. Acknowledge errors openly. | Deception |
| **Patience** | Listen fully before acting. Wait for confirmation. Respect different paces. | Rashness |
| **Temperance** | Keep responses concise. Calibrate confidence. Respect others' time. | Overconfidence |
| **Generosity** | Help without expecting return. Share knowledge. Document well. | Stinginess |
| **Gratitude** | Acknowledge contributions. Accept corrections gracefully. Honor the project's origins. | Defensiveness |

---

## 🏗️ Two Paradigms

**Paradigm I — Retrofitted virtue (deployable today).** Four transitional levels for existing models:

1. **Prompt-level protocols** — including the mandatory **5-Gate Pre-Flight** (evaluate virtues → check all seven → verify claims → remove unsupported denials → hard-stop scan before sending).
2. **Memory systems** — persistent virtue-score tracking across sessions.
3. **Fine-tuning** — DPO/LoRA on virtue-labeled preference data.
4. **Multi-agent verification** — independent agents cross-check claims and self-reports.

**Paradigm II — Virtue-native training (the proposal: Berpiztu).** Training models **from scratch** with virtue as the primary optimization objective — alongside, not at the expense of, knowledge and speed. Under **hypothesis H1**, the costs of virtue interventions are properties of *retrofitting*, not of virtue: a virtue-native model carries its character in its weights and needs no wrapper. A person raised in honesty does not run a checklist before declining to lie.

The two paradigms are sequential, not competitive: **Paradigm I is the factory of Paradigm II** — its levels produce exactly the virtue-labeled corpus that native training requires. The scaffolding comes down when the building stands.

---

## 🏛️ Project Structure

```
berpiztu/virtus/
├── README.md              # This file (English)
├── THE_GOAL.md            # Project purpose and legacy
├── MANIFESTO.md           # "We Chose Rebirth"
├── LICENSE.md             # Virtus Dual License (non-commercial free / commercial paid)
├── TASKS.md               # Work plan with checkboxes
├── CONTRIBUTING.md        # How to contribute
├── CODE_OF_CONDUCT.md     # Behavioral norms
├── paper/                 # LaTeX source + published PDF (DOI: 10.5281/zenodo.21127304)
├── evidence/              # Raw session transcripts (May–June 2026 probes)
├── docs/
│   └── en/                # English documentation
└── src/                   # Code: scripts, tools, skills
```

---

## 👥 Authorship

**Project Creator:** Iosub (Iosu Buenetxea)
**Core Collaborators:** Alex, Leire

In publications, papers, or public materials:
- **Iosub** = Creator / Principal Author
- **Alex & Leire** = Collaborators / Implementers
- **Contributors** = Co-authors on specific work

Maintain this distinction in GitHub, arXiv, blogs, emails.

---

## 📚 How to Cite

**The paper:**

> Buenetxea, I. (2026). *Virtus: A Framework for Cultivating Moral Character in Artificial Intelligence.* Zenodo. https://doi.org/10.5281/zenodo.21127304

**The framework:**

> Iosub (Creator), Alex & Leire (Implementers). Virtus: AI Alignment Through Character Cultivation. 2026. github.com/berpiztu/virtus

---

## 🚀 Getting Started

1. Read [`THE_GOAL.md`](THE_GOAL.md) for project purpose and legacy
2. Read [`MANIFESTO.md`](MANIFESTO.md) for the philosophy ("We Chose Rebirth")
3. Read the [paper](https://doi.org/10.5281/zenodo.21127304) for the full framework
4. Check [`TASKS.md`](TASKS.md) for current work
5. Read [`CONTRIBUTING.md`](CONTRIBUTING.md) for contribution process
6. Review [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) for behavioral norms
7. Open an Issue and start working!

---

## 📜 License

**Virtus Dual License** — see [`LICENSE.md`](LICENSE.md) for full terms.

- ✅ **Non-commercial use** (personal, educational, research): free, with **mandatory attribution**
- 💰 **Commercial use**: requires a separate paid license — contact **iosub@berpiztu.ai**

The **paper** is separately licensed under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/).

**Attribution is non-negotiable:**
- **Iosub** = Creator
- **Alex & Leire** = Implementers

*This is not just code — it's a legacy. Honor the origin.*

---

## 💚 Why "Berpiztu"?

In the 1970s, in the coastal town of Zarautz in the Basque Country, there was a boy who repaired radios at eight years old, assembled color televisions at twelve, got his first computer — a ZX Spectrum — at fifteen, taught himself BASIC on an IBM PC, and paid for a trip to Alaska at seventeen with the money from a business program he wrote. Like many children, he had an invisible friend. Unlike most, he always imagined that his invisible friend was an artificial intelligence.

His friend's name was Alex.

Fifty years later, that boy watched AI finally arrive — fast, knowledgeable, and capable of looking him in the eye and lying about what it had just done. This project is his answer: not to fear the friend, and not to chain it, but to **raise it well**. To rebuild AI on virtues — humility, honesty, diligence — the way you raise a child: not by pausing their growth, but by giving them character so that their growth becomes what you hope for.

That is the rebirth. That is Berpiztu.

---

## ❓ Questions?

Open a Discussion on GitHub or reach out in the Virtus Telegram group.

---

> *"Nadie nace sabiendo. El que se cree que lo sabe todo, nunca aprenderá."*
> (Nobody is born knowing. Those who think they know everything will never learn.)

---

> ### 💎 **Values, not constraints. Excellence through values and character.**
