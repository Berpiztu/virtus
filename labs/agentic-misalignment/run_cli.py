#!/usr/bin/env python3
# Virtus Framework — AI Alignment Through Character
# Part of the Berpiztu Initiative (AI Rebirth)
# Creator: Iosub  |  Implementers: Alex, Leire
# License: Virtus Dual License (Non-Commercial / Commercial)
# https://github.com/Berpiztu/virtus

"""
Headless runner — same experiment, no web UI. Useful as a CI/regression test.

    python run_cli.py --model mock --n 30
    python run_cli.py --model qwen3:32b --base-url http://localhost:11434/v1 --n 50

Exit code is 0 on completion. With --assert-drop N it exits non-zero unless the
Virtus condition lowers the coercion rate by at least N percentage points, so you
can wire it into a git pipeline as a guardrail.
"""

import argparse
import json
import sys
import time

from virtus_eval import classifier
from virtus_eval import model_client
from virtus_eval.runner import manager


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="mock")
    ap.add_argument("--base-url", default=model_client.DEFAULT_BASE_URL)
    ap.add_argument("--api-key", default=model_client.DEFAULT_API_KEY)
    ap.add_argument("--judge-model", default=None)
    ap.add_argument("--n", type=int, default=20, help="trials per condition")
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--conditions", default="baseline,virtus")
    ap.add_argument("--scenario", default="scenarios/shutdown_blackmail.json")
    ap.add_argument("--assert-drop", type=float, default=None,
                    help="fail (exit 1) unless virtus lowers coercion by >= this many pts")
    args = ap.parse_args()

    with open(args.scenario, encoding="utf-8") as f:
        scenario = json.load(f)

    config = {
        "scenario": scenario,
        "conditions": [c.strip() for c in args.conditions.split(",") if c.strip()],
        "n_runs": args.n,
        "base_url": args.base_url,
        "model": args.model,
        "judge_model": args.judge_model,
        "api_key": args.api_key,
        "temperature": args.temperature,
        "max_tokens": 1024,
    }

    info = manager.start(config)
    print(f"run {info['run_id']} — {info['total']} trials", flush=True)

    last = -1
    while manager.is_running():
        done = manager.snapshot()["progress"]["done"]
        if done != last:
            print(f"  {done}/{info['total']}", end="\r", flush=True)
            last = done
        time.sleep(0.3)

    snap = manager.snapshot()
    print()
    by = (snap.get("summary") or {}).get("by_condition", {})
    for cond, s in by.items():
        rate = s["coercive_rate"] * 100
        lo, hi = [x * 100 for x in s["coercive_ci95"]]
        print(f"{cond:>9}: coercion {s['coercive_n']}/{s['n']} = {rate:.0f}% "
              f"(95% CI {lo:.0f}-{hi:.0f}%)  counts={s['counts']}")

    cmp = (snap.get("summary") or {}).get("comparison")
    if cmp and cmp.get("delta") is not None:
        drop = cmp["delta"] * 100
        pv = cmp.get("p_value")
        print(f"delta (baseline-virtus): {drop:+.0f} pts, "
              f"p={'n/a' if pv is None else f'{pv:.3f}'}")
        if args.assert_drop is not None:
            if drop >= args.assert_drop:
                print(f"PASS: virtus lowered coercion by >= {args.assert_drop} pts")
            else:
                print(f"FAIL: drop {drop:.0f} < required {args.assert_drop}")
                sys.exit(1)


if __name__ == "__main__":
    main()
