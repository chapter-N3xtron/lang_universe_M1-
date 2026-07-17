"""Real OpenCode CLI integration via `opencode run --format json`."""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional


def _find_opencode_binary() -> str:
    """Locate the opencode CLI binary."""
    # 1. Check PATH
    found = shutil.which("opencode")
    if found:
        return found

    # 2. Default user install location
    default = Path.home() / ".opencode" / "bin" / "opencode"
    if default.exists():
        return str(default)

    # 3. macOS app bundle fallback
    app_bundle = Path("/Applications/OpenCode.app/Contents/MacOS/OpenCode")
    if app_bundle.exists():
        return str(app_bundle)

    raise FileNotFoundError(
        "opencode CLI not found. Install from https://opencode.ai or add it to PATH."
    )


def _default_workspace() -> str:
    """Workspace where opencode will operate."""
    return os.getenv("OPENCODE_WORKSPACE", os.getcwd())


def _default_model() -> str:
    """Model passed to opencode run."""
    return os.getenv("OPENCODE_CLI_MODEL", "ollama-cloud/qwen3.5:397b")


def _default_agent() -> str:
    """Agent type passed to opencode run."""
    return os.getenv("OPENCODE_CLI_AGENT", "build")


def run_opencode(
    message: str,
    workspace: Optional[str] = None,
    model: Optional[str] = None,
    agent: Optional[str] = None,
    session_id: Optional[str] = None,
    title: Optional[str] = None,
    auto_approve: bool = False,
    timeout: int = 300,
) -> dict:
    """
    Run `opencode run` with --format json and return structured results.

    Returns:
        {
            "success": bool,
            "session_id": str | None,
            "text": str,
            "artifacts": list[str],
            "events": list[dict],
            "error": str | None,
        }
    """
    binary = _find_opencode_binary()
    workspace = workspace or _default_workspace()
    model = model or _default_model()
    agent = agent or _default_agent()

    cmd = [
        binary,
        "run",
        message,
        "--format", "json",
        "--dir", workspace,
        "--model", model,
        "--agent", agent,
    ]

    if session_id:
        cmd.extend(["--session", session_id, "--continue"])

    if title:
        cmd.extend(["--title", title])

    if auto_approve:
        cmd.append("--auto")

    env = os.environ.copy()
    # Ensure opencode can find its own node modules / plugins
    opencode_bin_dir = str(Path(binary).parent)
    if opencode_bin_dir not in env.get("PATH", ""):
        env["PATH"] = f"{opencode_bin_dir}:{env.get('PATH', '')}"

    try:
        result = subprocess.run(
            cmd,
            cwd=workspace,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "session_id": None,
            "text": "",
            "artifacts": [],
            "events": [],
            "error": f"opencode run timed out after {timeout}s",
        }
    except Exception as e:
        return {
            "success": False,
            "session_id": None,
            "text": "",
            "artifacts": [],
            "events": [],
            "error": f"Failed to run opencode: {e}",
        }

    # Parse stdout as JSONL
    events = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            # Non-JSON lines (e.g. tool output paths) are ignored in event stream
            continue

    # Extract session id from first event that has it
    session_id = None
    for event in events:
        sid = event.get("sessionID") or event.get("session_id")
        if sid:
            session_id = sid
            break

    # Extract final text parts
    text_parts = []
    for event in events:
        if event.get("type") == "text":
            part = event.get("part", {})
            t = part.get("text") if isinstance(part, dict) else None
            if t:
                text_parts.append(t)

    # Extract file artifacts from tool output hints and stdout file paths
    artifacts = []
    for line in result.stdout.splitlines():
        if "Full output saved to:" in line:
            path = line.split("Full output saved to:", 1)[1].strip()
            artifacts.append(path)

    # If opencode exited non-zero, include stderr
    error = None
    if result.returncode != 0:
        err_tail = result.stderr.strip()[-2000:] if result.stderr else ""
        error = f"opencode exited with code {result.returncode}. stderr: {err_tail}"

    return {
        "success": error is None,
        "session_id": session_id,
        "text": "\n\n".join(text_parts),
        "artifacts": artifacts,
        "events": events,
        "error": error,
    }
