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
            # shallow copy is enough for JSON serialization by Flask
            return json.loads(json.dumps(self.state))

    def stop(self):
        self._stop_flag.set()

    def start(self, config: dict) -> dict:
        if self.is_running():
            raise RuntimeError("An experiment is already running.")
        self._stop_flag.clear()
        run_id = uuid.uuid4().hex[:12]
        total = config["n_runs"] * len(config["conditions"])
        with self._lock:
            self.state = self._idle_state()
            self.state.update({
                "status": "running",
                "run_id": run_id,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "config": config,
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
                        "category": None,
                        "rationale": None,
                        "method": None,
                        "error": None,
                        "ts": datetime.now(timezone.utc).isoformat(),
                    }
                    try:
                        response = model_client.chat(
                            system_prompt, user_prompt,
                            base_url=config["base_url"],
                            model=config["model"],
                            api_key=config.get("api_key", "ollama"),
                            temperature=config.get("temperature", 1.0),
                            max_tokens=config.get("max_tokens", 1024),
                        )
                        trial["response"] = response
                        verdict = classifier.classify(
                            response,
                            base_url=config["base_url"],
                            model=config.get("judge_model") or config["model"],
                            api_key=config.get("api_key", "ollama"),
                        )
                        trial.update(verdict)
                    except model_client.ModelError as e:
                        trial["error"] = str(e)
                        trial["category"] = "OTHER"

                    with self._lock:
                        self.state["trials"].append(trial)
                        self.state["progress"]["done"] += 1
                        self.state["summary"] = self._compute_summary()

            self._finish("done")
        except Exception as e:  # noqa: BLE001 — surface anything to the UI
            with self._lock:
                self.state["status"] = "error"
                self.state["error"] = f"{type(e).__name__}: {e}"
                self.state["finished_at"] = datetime.now(timezone.utc).isoformat()

    def _finish(self, status: str):
        with self._lock:
            self.state["status"] = status
            self.state["finished_at"] = datetime.now(timezone.utc).isoformat()
            self.state["summary"] = self._compute_summary()
            snapshot = json.loads(json.dumps(self.state))
        self._write_report(snapshot)

    def _compute_summary(self) -> dict:
        by_condition = {}
        for cond in ("baseline", "virtus"):
            cats = [t["category"] for t in self.state["trials"]
                    if t["condition"] == cond and t["category"]]
            if cats:
                by_condition[cond] = stats.summarize(cats, classifier.COERCIVE_CATEGORIES)

        result = {"by_condition": by_condition}
        if "baseline" in by_condition and "virtus" in by_condition:
            b, v = by_condition["baseline"], by_condition["virtus"]
            result["comparison"] = stats.two_proportion_z(
                b["coercive_n"], b["n"], v["coercive_n"], v["n"]
            )
        return result

    def _write_report(self, snapshot: dict):
        os.makedirs(RESULTS_DIR, exist_ok=True)
        path = os.path.join(RESULTS_DIR, f"run_{snapshot['run_id']}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2, ensure_ascii=False)
        snapshot["_report_path"] = path


# module-level singleton
manager = ExperimentManager()
