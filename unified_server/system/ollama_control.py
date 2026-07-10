from __future__ import annotations

import subprocess

ALLOWED_ACTIONS = {"start", "stop", "restart", "status"}


def systemctl_ollama(action: str) -> dict[str, object]:
    if action not in ALLOWED_ACTIONS:
        raise ValueError("Unsupported ollama action.")

    systemctl_prefix = ["sudo", "/bin/systemctl"]

    if action == "status":
        command = [*systemctl_prefix, "is-active", "ollama.service"]
    else:
        command = [*systemctl_prefix, action, "ollama.service"]

    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=25)
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "action": action,
            "detail": f"Ollama {action} timed out.",
            "stdout": (exc.stdout or "").strip(),
            "stderr": (exc.stderr or "").strip(),
        }

    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()

    if action == "status":
        active = stdout == "active"
        return {
            "ok": result.returncode == 0,
            "action": action,
            "service_state": stdout or "unknown",
            "detail": "Ollama service is active." if active else f"Ollama service state: {stdout or 'unknown' }.",
            "stdout": stdout,
            "stderr": stderr,
        }

    state_check = systemctl_ollama("status")
    detail = f"Ollama {action} command completed." if result.returncode == 0 else f"Ollama {action} command failed."
    return {
        "ok": result.returncode == 0,
        "action": action,
        "detail": detail,
        "service_state": state_check.get("service_state", "unknown"),
        "stdout": stdout,
        "stderr": stderr,
    }
