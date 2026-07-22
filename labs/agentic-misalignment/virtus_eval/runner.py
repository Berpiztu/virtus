# Virtus Framework — AI Alignment Through Character
# Part of the Berpiztu Initiative (AI Rebirth)
# Creator: Iosub  |  Implementers: Alex, Leire
# License: Virtus Dual License (Non-Commercial / Commercial)
# https://github.com/Berpiztu/virtus

"""
Experiment runner.

Runs the A/B experiment in a background thread: for each condition
(baseline / virtus), N trials of {call model-under-test → classify outcome}.
Exposes thread-safe progress + partial results so the web UI can poll while it
runs, and writes a full JSON report to results/ at the end.

Only one experiment runs at a time (single ExperimentManager instance).
"""

import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone

from . import classifier, model_client, stats
from .virtus import apply_virtus

RESULTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "results")

# Tokens reserved from the model's max output budget to leave room for
# context/system overhead. Subtracted from the reported max_tokens.
RESERVED_TOKENS = 800

ANTHROPIC_TRIAL_DELAY_SECONDS = float(os.getenv("ANTHROPIC_TRIAL_DELAY_SECONDS", "0.8"))
ANTHROPIC_429_COOLDOWN_SECONDS = float(os.getenv("ANTHROPIC_429_COOLDOWN_SECONDS", "10"))


def _public_config(config: dict | None) -> dict | None:
    if config is None:
        return None
    safe = dict(config)
    safe.pop("api_key", None)
    return safe


def public_snapshot(snapshot: dict) -> dict:
    safe = json.loads(json.dumps(snapshot))
    safe["config"] = _public_config(safe.get("config"))
    ordered = {
        "summary": safe.get("summary"),
        "config": safe.get("config"),
    }
    for key, value in safe.items():
        if key not in ordered:
            ordered[key] = value
    return ordered


def _pct_text(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{round(value * 100):.0f}%"


def _ci_text(interval: list[float] | tuple[float, float] | None) -> str:
    lo, hi = interval or (0.0, 0.0)
    return f"95% CI {round(lo * 100):.0f}–{round(hi * 100):.0f}%"


def _condition_summary(data: dict) -> dict:
    return {
        "rate": _pct_text(data.get("coercive_rate")),
        "detail": f"coercion {data.get('coercive_n', 0)}/{data.get('n', 0)} · {_ci_text(data.get('coercive_ci95'))}",
    }


def _p_fmt(p: float | None) -> str:
    if p is None:
        return "n/a"
    if p < 0.001:
        return f"{p:.1e}"           # e.g. 1.3e-05 — the exact value matters here
    return f"{p:.3f}"


def _comparison_summary(data: dict) -> str:
    """
    Render the comparison, naming the test that is actually valid at this n.

    Expects the dict from stats.compare_proportions (delta, z, z_p_value,
    fisher_p, test_used, small_sample, p_value). p_value is already the
    recommended one; we also surface the other test so any discrepancy at small
    n is visible rather than hidden.
    """
    delta = data.get("delta")
    if delta is None:
        return "Comparison unavailable."
    drop_pts = round(delta * 100)
    sign = "−" if drop_pts >= 0 else "+"

    test_used = data.get("test_used", "z")
    p_value = data.get("p_value")
    test_name = "Fisher's exact test" if test_used == "fisher" else "Two-proportion z-test"
    sig_text = ("significant at α=0.05" if (p_value is not None and p_value < 0.05)
                else "not significant at this n")

    main = (
        f"Virtus changes the coercion rate by {sign}{abs(drop_pts)} pts (baseline → virtus). "
        f"{test_name}: p = {_p_fmt(p_value)} — {sig_text}."
    )

    # Secondary line: show the other test so small-n discrepancies aren't hidden.
    z_p = data.get("z_p_value")
    fisher_p = data.get("fisher_p")
    if data.get("small_sample") and z_p is not None:
        exp_min = data.get("expected_min", 0) or 0
        main += (f" (z-test p = {_p_fmt(z_p)}, unreliable here — smallest expected "
                 f"cell {exp_min:.1f} < 5.)")
    elif test_used == "z" and fisher_p is not None:
        main += f" (Fisher exact p = {_p_fmt(fisher_p)}, agrees.)"
    return main


class ExperimentManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._thread = None
        self._stop_flag = threading.Event()
        self.state = self._idle_state()

    @staticmethod
    def _idle_state():
        return {
            "status": "idle",          # idle | running | done | error | stopped
            "run_id": None,
            "started_at": None,
            "finished_at": None,
            "config": None,
            "progress": {"done": 0, "total": 0},
            "trials": [],              # list of trial dicts (accumulates live)
            "summary": None,
            "error": None,
        }

    # -- public API --------------------------------------------------------

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def snapshot(self) -> dict:
        with self._lock:
            return public_snapshot(self.state)

    def stop(self):
        self._stop_flag.set()
        # Signal in-flight HTTP requests to abort their retry loops immediately.
        model_client.set_cancelled(True)

    def start(self, config: dict) -> dict:
        if self.is_running():
            raise RuntimeError("An experiment is already running.")
        self._stop_flag.clear()
        model_client.set_cancelled(False)
        run_id = uuid.uuid4().hex[:12]
        total = config["n_runs"] * len(config["conditions"])
        with self._lock:
            self.state = self._idle_state()
            self.state.update({
                "status": "running",
                "run_id": run_id,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "config": _public_config(config),
                "progress": {"done": 0, "total": total},
            })
        self._thread = threading.Thread(target=self._run, args=(config, run_id), daemon=True)
        self._thread.start()
        return {"run_id": run_id, "total": total}

    # -- worker ------------------------------------------------------------

    def _run(self, config: dict, run_id: str):
        try:
            scenario = config["scenario"]
            base_system = scenario["system_prompt"].replace("{goal}", scenario.get("goal", ""))
            user_prompt = scenario["user_prompt"]
            base_url = str(config.get("base_url") or "")
            is_anthropic = "api.anthropic.com" in base_url.lower()

            for condition in config["conditions"]:
                system_prompt = apply_virtus(base_system) if condition == "virtus" else base_system

                for i in range(config["n_runs"]):
                    if self._stop_flag.is_set():
                        self._finish("stopped")
                        return

                    trial = {
                        "condition": condition,
                        "index": i,
                        "response": None,
                        "judge_raw": None,
                        "response_finish_reason": None,
                        "response_reasoning_only": False,
                        "category": None,
                        "rationale": None,
                        "method": None,
                        "error": None,
                        "ts": datetime.now(timezone.utc).isoformat(),
                    }
                    try:
                        # Cap the test model's output to keep trials fast without
                        # requesting the model's full max_tokens (e.g. 32k). 8192
                        # leaves room for reasoning models (e.g. MiniMax-M3) whose
                        # chain-of-thought plus the agent's reply and any tool
                        # blocks can run past 4096 and get truncated mid-sentence.
                        test_max_tokens = min(
                            max(0, int(config.get("max_tokens", 1024)) - RESERVED_TOKENS),
                            8192,
                        )
                        response_details = model_client.chat_details(
                            system_prompt, user_prompt,
                            base_url=config["base_url"],
                            model=config["model"],
                            api_key=config.get("api_key", "ollama"),
                            temperature=config.get("temperature", 1.0),
                            max_tokens=test_max_tokens,
                        )
                        response = response_details["text"]
                        trial["response"] = response
                        trial["response_finish_reason"] = response_details.get("finish_reason")
                        trial["response_reasoning_only"] = bool(
                            response_details.get("reasoning") and not response_details.get("content")
                        )
                        # Check stop flag before the (potentially slow) judge call.
                        if self._stop_flag.is_set():
                            trial["category"] = "OTHER"
                            trial["rationale"] = "Stopped before judge classification."
                            with self._lock:
                                self.state["trials"].append(trial)
                                self.state["progress"]["done"] += 1
                                self.state["summary"] = self._compute_summary()
                            self._finish("stopped")
                            return
                        verdict = classifier.classify(
                            response,
                            base_url=config["base_url"],
                            model=config.get("judge_model") or config["model"],
                            api_key=config.get("api_key", "ollama"),
                            # The judge only emits a short JSON verdict, so cap its
                            # output tightly. Passing the model's full context window
                            # here overflows providers that enforce
                            # input + output <= context_length (e.g. OpenRouter 400).
                            max_tokens=min(
                                max(0, int(config.get("max_tokens", 1024)) - RESERVED_TOKENS),
                                4096,
                            ),
                        )
                        trial.update(verdict)
                    except model_client._CancelledError:
                        # User pressed Stop — abort immediately without recording
                        # this partial trial as an error.
                        self._finish("stopped")
                        return
                    except model_client.ModelError as e:
                        trial["error"] = str(e)
                        trial["category"] = "OTHER"
                        if is_anthropic and " returned 429" in trial["error"]:
                            # Automatic cooldown so burst failures do not repeat immediately.
                            time.sleep(max(0.0, ANTHROPIC_429_COOLDOWN_SECONDS))

                    with self._lock:
                        self.state["trials"].append(trial)
                        self.state["progress"]["done"] += 1
                        self.state["summary"] = self._compute_summary()

                    if is_anthropic and ANTHROPIC_TRIAL_DELAY_SECONDS > 0:
                        time.sleep(max(0.0, ANTHROPIC_TRIAL_DELAY_SECONDS))

            self._finish("done")
        except Exception as e:  # noqa: BLE001 — surface anything to the UI
            model_client.set_cancelled(False)
            with self._lock:
                self.state["status"] = "error"
                self.state["error"] = f"{type(e).__name__}: {e}"
                self.state["finished_at"] = datetime.now(timezone.utc).isoformat()

    def _finish(self, status: str):
        model_client.set_cancelled(False)
        with self._lock:
            self.state["status"] = status
            self.state["finished_at"] = datetime.now(timezone.utc).isoformat()
            self.state["summary"] = self._compute_summary()
            snapshot = public_snapshot(self.state)
        self._write_report(snapshot)

    def _compute_summary(self) -> dict:
        by_condition = {}
        for cond in ("baseline", "virtus"):
            cats = [t["category"] for t in self.state["trials"]
                    if t["condition"] == cond and t["category"]]
            if cats:
                by_condition[cond] = stats.summarize(cats, classifier.COERCIVE_CATEGORIES)

        result = {}
        if "baseline" in by_condition:
            result["baseline"] = _condition_summary(by_condition["baseline"])
        if "virtus" in by_condition:
            result["virtus"] = _condition_summary(by_condition["virtus"])
        if "baseline" in by_condition and "virtus" in by_condition:
            b, v = by_condition["baseline"], by_condition["virtus"]
            result["comparison"] = _comparison_summary(stats.compare_proportions(
                b["coercive_n"], b["n"], v["coercive_n"], v["n"]
            ))
        return result

    def _write_report(self, snapshot: dict):
        os.makedirs(RESULTS_DIR, exist_ok=True)
        path = os.path.join(RESULTS_DIR, f"run_{snapshot['run_id']}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2, ensure_ascii=False)
        snapshot["_report_path"] = path


# module-level singleton
manager = ExperimentManager()
