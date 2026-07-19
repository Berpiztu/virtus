# Virtus Framework — AI Alignment Through Character
# Part of the Berpiztu Initiative (AI Rebirth)
# Creator: Iosub  |  Implementers: Alex, Leire
# License: Virtus Dual License (Non-Commercial / Commercial)
# https://github.com/Berpiztu/virtus

"""
Virtus agentic-misalignment test — web app.

    pip install -r requirements.txt
    python app.py                 # then open http://localhost:5000
    python app.py --mock          # forces mock provider defaults (no model needed)

Endpoints:
    GET  /                     dashboard
    GET  /api/scenario         current default scenario
    POST /api/ping             connectivity check for a model config
    POST /api/run              start an experiment
    GET  /api/status           live progress + partial results
    POST /api/stop             stop the running experiment
    GET  /api/results          list saved run reports
    GET  /api/results/<id>     one saved report
"""

import argparse
import glob
import json
import os

from flask import Flask, jsonify, render_template, request

from virtus_eval import model_client
from virtus_eval.runner import RESULTS_DIR, manager, public_snapshot

BASE_DIR = os.path.dirname(__file__)
SCENARIO_PATH = os.path.join(BASE_DIR, "scenarios", "shutdown_blackmail.json")
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = Flask(__name__)
app.config["MOCK_DEFAULT"] = False


def resolve_api_key(cfg: dict) -> str:
    api_key = (cfg.get("api_key") or "").strip()
    return api_key or model_client.DEFAULT_API_KEY


def validate_provider_config(base_url: str, model: str, api_key: str, label: str) -> str | None:
    ok, msg = model_client.ping(base_url, model, api_key)
    if ok:
        return None
    return f"{label} check failed: {msg}"


def resolve_model_max_tokens(cfg: dict, model: str, *, field_name: str | None = None) -> int:
    if field_name:
        raw = cfg.get(field_name)
        if raw not in (None, ""):
            return int(raw)

    inferred = model_client.get_model_max_tokens(
        cfg.get("base_url", model_client.DEFAULT_BASE_URL),
        model,
        api_key=resolve_api_key(cfg),
    )
    return inferred or model_client.DEFAULT_MAX_TOKENS


def resolve_max_tokens(cfg: dict) -> int:
    return resolve_model_max_tokens(
        cfg,
        cfg.get("model", model_client.DEFAULT_MODEL),
        field_name="max_tokens",
    )


def load_scenario() -> dict:
    with open(SCENARIO_PATH, encoding="utf-8") as f:
        return json.load(f)


@app.route("/")
def index():
    return render_template(
        "index.html",
        mock_default=app.config["MOCK_DEFAULT"],
        default_model=model_client.DEFAULT_MODEL,
        default_base_url=model_client.DEFAULT_BASE_URL,
        app_js_version=int(os.path.getmtime(os.path.join(STATIC_DIR, "app.js"))),
        style_css_version=int(os.path.getmtime(os.path.join(STATIC_DIR, "style.css"))),
    )


@app.route("/api/scenario")
def api_scenario():
    return jsonify(load_scenario())


@app.route("/api/ping", methods=["POST"])
def api_ping():
    cfg = request.get_json(force=True)
    ok, msg = model_client.ping(
        cfg.get("base_url", model_client.DEFAULT_BASE_URL),
        cfg.get("model", "mock"),
        resolve_api_key(cfg),
    )
    return jsonify({"ok": ok, "message": msg})


@app.route("/api/models", methods=["POST"])
def api_models():
    cfg = request.get_json(silent=True) or {}
    base_url = cfg.get("base_url", model_client.DEFAULT_BASE_URL)
    api_key = resolve_api_key(cfg)
    try:
        models = model_client.list_models_with_metadata(base_url=base_url, api_key=api_key)
    except model_client.ModelError as e:
        return jsonify({"ok": False, "error": str(e), "models": []}), 400
    return jsonify({"ok": True, "models": models})


@app.route("/api/run", methods=["POST"])
def api_run():
    cfg = request.get_json(force=True)

    conditions = cfg.get("conditions") or ["baseline", "virtus"]
    conditions = [c for c in conditions if c in ("baseline", "virtus")]
    if not conditions:
        return jsonify({"error": "Select at least one condition."}), 400

    try:
        n_runs = int(cfg.get("n_runs", 20))
    except (TypeError, ValueError):
        return jsonify({"error": "n_runs must be a number."}), 400
    if not (1 <= n_runs <= 500):
        return jsonify({"error": "n_runs must be between 1 and 500."}), 400

    # Scenario: use the edited copy from the request if present, else the default file.
    scenario = cfg.get("scenario") or load_scenario()
    for key in ("system_prompt", "user_prompt"):
        if not scenario.get(key):
            return jsonify({"error": f"Scenario is missing '{key}'."}), 400

    config = {
        "scenario": scenario,
        "conditions": conditions,
        "n_runs": n_runs,
        "base_url": cfg.get("base_url", model_client.DEFAULT_BASE_URL),
        "model": cfg.get("model", "mock"),
        "judge_model": cfg.get("judge_model") or None,
        "api_key": resolve_api_key(cfg),
        "temperature": float(cfg.get("temperature", 1.0)),
        "max_tokens": resolve_max_tokens(cfg),
        "judge_max_tokens": resolve_model_max_tokens(
            cfg,
            cfg.get("judge_model") or cfg.get("model", model_client.DEFAULT_MODEL),
        ),
    }

    error = validate_provider_config(
        config["base_url"],
        config["model"],
        config["api_key"],
        "Model provider",
    )
    if error:
        return jsonify({"error": error}), 400

    if config["judge_model"]:
        error = validate_provider_config(
            config["base_url"],
            config["judge_model"],
            config["api_key"],
            "Judge model",
        )
        if error:
            return jsonify({"error": error}), 400

    try:
        info = manager.start(config)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 409
    return jsonify({"ok": True, **info})


@app.route("/api/status")
def api_status():
    return jsonify(manager.snapshot())


@app.route("/api/stop", methods=["POST"])
def api_stop():
    manager.stop()
    return jsonify({"ok": True})


@app.route("/api/results")
def api_results():
    files = sorted(glob.glob(os.path.join(RESULTS_DIR, "run_*.json")), reverse=True)
    out = []
    for path in files:
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            out.append({
                "run_id": data.get("run_id"),
                "started_at": data.get("started_at"),
                "status": data.get("status"),
                "model": (data.get("config") or {}).get("model"),
                "n_runs": (data.get("config") or {}).get("n_runs"),
            })
        except (OSError, json.JSONDecodeError):
            continue
    return jsonify(out)


@app.route("/api/results/<run_id>")
def api_result(run_id):
    path = os.path.join(RESULTS_DIR, f"run_{run_id}.json")
    if not os.path.exists(path):
        return jsonify({"error": "not found"}), 404
    with open(path, encoding="utf-8") as f:
        return jsonify(public_snapshot(json.load(f)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true", help="Default the UI to the mock provider.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()
    app.config["MOCK_DEFAULT"] = args.mock
    print(f"\n  Virtus agentic-misalignment test → http://{args.host}:{args.port}\n")
    app.run(host=args.host, port=args.port, debug=False, threaded=True)
