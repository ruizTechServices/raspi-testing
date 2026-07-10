from __future__ import annotations

from flask import Blueprint, jsonify, request

from unified_server.security import require_api_key
from unified_server.system.llm_status import get_llm_status_snapshot
from unified_server.system.ollama_control import ALLOWED_ACTIONS, systemctl_ollama
from unified_server.system.temperature import PiTemperatureMonitor


def build_system_blueprint(temperature_monitor: PiTemperatureMonitor | None = None) -> Blueprint:
    bp = Blueprint("system", __name__)
    monitor = temperature_monitor or PiTemperatureMonitor()

    @bp.get("/api/system/temperature")
    def system_temperature():
        try:
            return jsonify({"status": "ok", **monitor.snapshot()})
        except Exception as exc:
            return jsonify({"error": f"Unable to read Pi temperature: {exc}"}), 503

    @bp.get("/api/system/llm-status")
    def system_llm_status():
        try:
            return jsonify(get_llm_status_snapshot())
        except Exception as exc:
            return jsonify({"error": f"Unable to check LLM status: {exc}"}), 503

    @bp.post("/api/system/ollama/control")
    @require_api_key
    def system_ollama_control():
        payload = request.get_json(silent=True) or {}
        action = str(payload.get("action", "")).strip().lower()
        if action not in ALLOWED_ACTIONS:
            return jsonify({"error": "Invalid Ollama action. Use start, stop, restart, or status."}), 400
        try:
            result = systemctl_ollama(action)
            status_code = 200 if result.get("ok") else 503
            return jsonify({"status": "ok" if result.get("ok") else "error", **result}), status_code
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"error": f"Unable to control Ollama service: {exc}"}), 503

    return bp
