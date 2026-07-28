"""Real OpenCode CLI integration via `opencode run --format json`."""

import asyncio
import json
import os
import shutil
import subprocess
from pathlib import Path

from src.ollama_client import chat_ollama


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


def _is_local_ollama_model(model: str | None) -> bool:
    return bool(model and model.startswith("ollama/") and not model.startswith("ollama-cloud/"))


def run_opencode(
    message: str,
    workspace: str | None = None,
    model: str | None = None,
    agent: str | None = None,
    session_id: str | None = None,
    title: str | None = None,
    auto_approve: bool = False,
    timeout: int = 300,
    history: list | None = None,
) -> dict:
    """
    Run `opencode run` with --format json and return structured results.

    For local Ollama models (prefix `ollama/`), bypass the OpenCode CLI and
    call the local Ollama API directly because the OpenCode CLI only
    supports the `ollama-cloud` provider.

    For cloud/OpenCode models, a `session_id` should be supplied on every
    subsequent turn to continue the same CLI session. The returned
    `session_id` should be stored per conversation thread and passed back
    on the next invocation.

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
    model = model or _default_model()

    if _is_local_ollama_model(model):
        result = chat_ollama(
            message=message,
            model=model,
            history=history,
            timeout=timeout,
        )
        return {
            "success": result["success"],
            "session_id": None,
            "text": result["text"],
            "artifacts": [],
            "events": [],
            "error": result.get("error"),
        }

    binary = _find_opencode_binary()
    workspace = workspace or _default_workspace()
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

    # Reuse an existing OpenCode CLI session when possible so the headless
    # agent retains its own conversation context across turns.
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


async def run_opencode_stream(
    message: str,
    workspace: str | None = None,
    model: str | None = None,
    agent: str | None = None,
    session_id: str | None = None,
    title: str | None = None,
    auto_approve: bool = False,
    timeout: int = 300,
    history: list | None = None,
) -> dict:
    """
    Async streaming variant of run_opencode.

    Yields parsed JSONL events as they arrive from the subprocess stdout.
    For local Ollama models, falls back to sync chat_ollama and yields
    a single text event followed by a complete event.

    Yields:
        dict with at least a ``type`` key:
        - {"type": "text", "text": str, "session_id": str | None}
        - {"type": "complete", "text": str, "session_id": str | None, "artifacts": list[str]}
        - {"type": "error", "error": str}
    """
    model = model or _default_model()

    if _is_local_ollama_model(model):
        result = chat_ollama(
            message=message,
            model=model,
            history=history,
            timeout=timeout,
        )
        if result.get("text"):
            yield {"type": "text", "text": result["text"], "session_id": None}
        if result["success"]:
            yield {"type": "complete", "text": result.get("text", ""), "session_id": None, "artifacts": []}
        else:
            yield {"type": "error", "error": result.get("error", "Ollama call failed")}
        return

    binary = _find_opencode_binary()
    workspace = workspace or _default_workspace()
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
    opencode_bin_dir = str(Path(binary).parent)
    if opencode_bin_dir not in env.get("PATH", ""):
        env["PATH"] = f"{opencode_bin_dir}:{env.get('PATH', '')}"

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=workspace,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except Exception as e:
        yield {"type": "error", "error": f"Failed to start opencode: {e}"}
        return

    if proc.stdout is None:
        yield {"type": "error", "error": "No stdout from opencode subprocess"}
        return

    assert proc.stderr is not None

    text_parts: list[str] = []
    artifacts: list[str] = []
    found_session_id: str | None = None
    stderr_lines: list[str] = []

    async def _read_stderr():
        async for line in proc.stderr:
            stderr_lines.append(line.decode("utf-8", errors="replace"))

    stderr_task = asyncio.create_task(_read_stderr())

    try:
        async for line_byte in proc.stdout:
            line = line_byte.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                if "Full output saved to:" in line:
                    path = line.split("Full output saved to:", 1)[1].strip()
                    artifacts.append(path)
                continue

            sid = event.get("sessionID") or event.get("session_id")
            if sid:
                found_session_id = sid

            if event.get("type") == "text":
                part = event.get("part", {})
                t = part.get("text") if isinstance(part, dict) else None
                if t:
                    text_parts.append(t)
                    yield {
                        "type": "text",
                        "text": t,
                        "session_id": found_session_id,
                    }
    except asyncio.TimeoutError:
        proc.kill()
        yield {
            "type": "error",
            "error": f"opencode run timed out after {timeout}s",
        }
        return

    await stderr_task
    await proc.wait()

    full_text = "\n\n".join(text_parts)
    error = None
    if proc.returncode and proc.returncode != 0:
        err_tail = "".join(stderr_lines)[-2000:] if stderr_lines else ""
        error = f"opencode exited with code {proc.returncode}. stderr: {err_tail}"

    if error:
        yield {"type": "error", "error": error}
    else:
        yield {
            "type": "complete",
            "text": full_text,
            "session_id": found_session_id,
            "artifacts": artifacts,
        }
