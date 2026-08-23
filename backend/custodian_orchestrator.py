#!/usr/bin/env python3
"""
Local Custodian Orchestrator.

This is the local coding-agent runtime between Open WebUI and the lower-level
Custodian worker. Open WebUI sends one request here; this service owns the
model/tool loop and calls the worker for repo, terminal, git, Docker, memory,
graph, and search actions.
"""

from __future__ import annotations

import json
import os
import re
import ssl
import time
import traceback
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
WRAPPER_PATH = BASE_DIR / "the_custodian_wrapper.md"
LOG_DIR = BASE_DIR / "logs" / "orchestrator"


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text().splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#") or "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        value = value.rstrip("\r")
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        values[key.strip()] = value
    return values


ENV = {**load_env(ENV_PATH), **os.environ}
BIND_HOST = ENV.get("CUSTODIAN_ORCHESTRATOR_BIND_HOST", "127.0.0.1")
PORT = int(ENV.get("CUSTODIAN_ORCHESTRATOR_PORT", "8767"))


def orchestrator_worker_url(env: dict[str, str]) -> str:
    return env.get(
        "CUSTODIAN_ORCHESTRATOR_WORKER_URL", "http://127.0.0.1:8765"
    ).rstrip("/")


WORKER_URL = orchestrator_worker_url(ENV)
OPENAI_URL = ENV.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_MODEL = ENV.get("OPENAI_MODEL", "gpt-5.5")
OPENAI_TLS_VERIFY = ENV.get("OPENAI_TLS_VERIFY", "true").lower() not in {"0", "false", "no"}
MAX_TOOL_CALLS = int(ENV.get("CUSTODIAN_ORCHESTRATOR_MAX_TOOL_CALLS", "8"))
MODEL_TIMEOUT = int(ENV.get("CUSTODIAN_ORCHESTRATOR_MODEL_TIMEOUT", "120"))
WORKER_TIMEOUT = int(ENV.get("CUSTODIAN_ORCHESTRATOR_WORKER_TIMEOUT", "90"))
MAX_TOOL_OUTPUT_CHARS = int(ENV.get("CUSTODIAN_ORCHESTRATOR_MAX_TOOL_OUTPUT_CHARS", "6000"))
API_TOKEN_FILE = Path(
    ENV.get("CUSTODIAN_API_TOKEN_FILE") or BASE_DIR / ".custodian_api_token"
).expanduser()


def custodian_api_token() -> str:
    value = ENV.get("CUSTODIAN_API_TOKEN", "").strip()
    if value:
        return value
    try:
        token = API_TOKEN_FILE.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError("Custodian authentication token is unavailable.") from exc
    if len(token) < 32:
        raise RuntimeError("Custodian authentication token is invalid.")
    return token


SECRET_REDACTIONS = [
    (re.compile(r"sk-[A-Za-z0-9_\-]{20,}"), "sk-REDACTED"),
    (re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{30,}\b"), "TELEGRAM_TOKEN_REDACTED"),
    (
        re.compile(
            r"(?i)(api[_-]?key|secret|token|password)(\s*[:=]\s*)['\"]?([^'\"\s]{8,})['\"]?"
        ),
        r"\1\2REDACTED",
    ),
    (
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
            re.S,
        ),
        "PRIVATE_KEY_BLOCK_REDACTED",
    ),
]


def redact_text(value: Any) -> str:
    text = "" if value is None else str(value)
    for pattern, replacement in SECRET_REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


def clip_text(value: Any, limit: int = MAX_TOOL_OUTPUT_CHARS) -> str:
    text = redact_text(value)
    if len(text) <= limit:
        return text
    omitted = len(text) - limit
    return f"[output clipped: {omitted} chars omitted]\n{text[-limit:]}"


def read_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0:
        return {}
    raw = handler.rfile.read(length).decode("utf-8")
    return json.loads(raw) if raw else {}


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def http_json(url: str, payload: dict[str, Any] | None = None, timeout: int = 60) -> dict[str, Any]:
    data = None
    method = "GET"
    headers = {
        "Authorization": f"Bearer {custodian_api_token()}",
        "Content-Type": "application/json",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        method = "POST"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def tls_context() -> ssl.SSLContext | None:
    if not OPENAI_TLS_VERIFY:
        return ssl._create_unverified_context()
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return None


def worker_task(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    worker_payload = dict(payload)
    try:
        if action in {"fs_write", "fs_edit"}:
            revision = http_json(
                f"{WORKER_URL}/task",
                {
                    "action": "fs_revision",
                    "repo": worker_payload.get("repo", ""),
                    "path": worker_payload.get("path", ""),
                },
                timeout=WORKER_TIMEOUT,
            )
            worker_payload["expected_revision"] = revision["result"]["revision"]
        worker_payload["action"] = action
        return http_json(f"{WORKER_URL}/task", worker_payload, timeout=WORKER_TIMEOUT)
    except Exception as error:
        return {
            "ok": False,
            "selected_action": action,
            "error": f"Worker request failed: {error}",
        }


def worker_status() -> dict[str, Any]:
    try:
        return http_json(f"{WORKER_URL}/status", timeout=10)
    except Exception as error:
        return {"ok": False, "error": str(error)}


def read_wrapper() -> str:
    if not WRAPPER_PATH.exists():
        return "You are The Custodian, a local coding agent for FrnT_DESK."
    return WRAPPER_PATH.read_text(errors="replace")


def tool_schema() -> list[dict[str, Any]]:
    actions = [
        "command",
        "read_file",
        "write_file",
        "replace_text",
        "git",
        "compose_read",
    ]
    return [
        {
            "type": "function",
            "name": "custodian_tool",
            "description": (
                "Run one controlled Custodian tool. Use this for repo inspection, "
                "small patch-based edits, git diff/status, Docker checks, memory/search, "
                "or graph queries. Prefer small, targeted calls."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": actions,
                        "description": "The controlled action to run.",
                    },
                    "path": {
                        "type": "string",
                        "description": "Repo-relative path for file actions.",
                    },
                    "argv": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "description": "Argument vector; shell command strings are forbidden.",
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Repo-relative working directory.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Content for write_file.",
                    },
                    "old_text": {
                        "type": "string",
                        "description": "Exact text to replace.",
                    },
                    "new_text": {
                        "type": "string",
                        "description": "Replacement text.",
                    },
                    "patch": {
                        "type": "string",
                        "description": "Unified diff patch for apply_patch.",
                    },
                    "query": {
                        "type": "string",
                        "description": "Search, memory, or graph query.",
                    },
                    "collection": {
                        "type": "string",
                        "description": "Optional memory collection/tool name.",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Command timeout in seconds.",
                    },
                },
                "required": ["action"],
                "additionalProperties": False,
            },
        }
    ]


def map_tool_action(args: dict[str, Any], base_payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    action = str(args.get("action") or "").strip()
    payload = dict(base_payload)
    payload.update(
        {
            "path": args.get("path", ""),
            "argv": args.get("argv", []),
            "cwd": args.get("cwd", "."),
            "content": args.get("content", ""),
            "old_text": args.get("old_text", ""),
            "new_text": args.get("new_text", ""),
            "patch": args.get("patch", ""),
            "timeout": args.get("timeout", 60),
        }
    )

    if action == "read_file":
        return "fs_read", payload
    if action == "write_file":
        return "fs_write", payload
    if action == "replace_text":
        payload["old_string"] = payload.pop("old_text")
        payload["new_string"] = payload.pop("new_text")
        return "fs_edit", payload
    return action, payload


def text_from_response(data: dict[str, Any]) -> str:
    texts: list[str] = []
    for item in data.get("output", []) or []:
        if item.get("type") == "message":
            for content in item.get("content", []) or []:
                if content.get("type") in {"output_text", "text"}:
                    texts.append(content.get("text", ""))
        elif item.get("type") == "output_text":
            texts.append(item.get("text", ""))
    if texts:
        return "\n".join(texts).strip()
    return str(data.get("output_text") or "").strip()


def function_calls(data: dict[str, Any]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for item in data.get("output", []) or []:
        if item.get("type") == "function_call":
            calls.append(item)
    return calls


def openai_response(
    input_items: list[dict[str, Any]],
    *,
    instructions: str | None = None,
    previous_response_id: str | None = None,
) -> dict[str, Any]:
    api_key = ENV.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set in custodian/.env.")
    payload: dict[str, Any] = {
        "model": OPENAI_MODEL,
        "input": input_items,
        "tools": tool_schema(),
    }
    if instructions:
        payload["instructions"] = instructions
    if previous_response_id:
        payload["previous_response_id"] = previous_response_id
    request = urllib.request.Request(
        f"{OPENAI_URL}/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=MODEL_TIMEOUT, context=tls_context()) as response:
        return json.loads(response.read().decode("utf-8"))


@dataclass
class RunState:
    run_id: str
    request: str
    repo: str
    context: str
    started_at: float
    tool_calls: list[dict[str, Any]]
    final: str = ""
    error: str = ""


def log_run(state: RunState) -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / f"{int(state.started_at)}-{state.run_id}.json"
    payload = {
        "run_id": state.run_id,
        "request": state.request,
        "repo": state.repo,
        "context": state.context,
        "started_at": state.started_at,
        "finished_at": time.time(),
        "tool_calls": state.tool_calls,
        "final": state.final,
        "error": state.error,
    }
    path.write_text(json.dumps(payload, indent=2))
    return path


def run_orchestrator(payload: dict[str, Any]) -> dict[str, Any]:
    request_text = str(payload.get("request") or "").strip()
    if not request_text:
        return {"ok": False, "error": "Missing request.", "action": "ask_custodian"}
    if not str(payload.get("repo") or "").startswith("/"):
        return {"ok": False, "error": "An exact absolute selected repository is required.", "action": "ask_custodian"}

    state = RunState(
        run_id=str(uuid.uuid4()),
        request=request_text,
        repo=str(payload.get("repo") or ""),
        context=str(payload.get("context") or ""),
        started_at=time.time(),
        tool_calls=[],
    )

    worker = worker_status()
    system = (
        read_wrapper()
        + "\n\n## Orchestrator Rules\n"
        + "- You are running inside the local Custodian Orchestrator, not directly inside OWUI.\n"
        + "- Use `custodian_tool` for repo, terminal, file, git, Docker, search, memory, and graph actions.\n"
        + "- Prefer read -> small patch -> git diff/status -> verification.\n"
        + "- Do not claim work is complete unless tool results support it.\n"
        + "- Keep commands short and targeted. Do not dump large files or logs.\n"
        + "- If a tool is missing or blocked, report the exact blocker.\n"
    )

    user = (
        f"Request:\n{request_text}\n\n"
        f"Selected repo hint: {state.repo or '(use worker selected repo)'}\n\n"
        f"Context:\n{state.context or '(none)'}\n\n"
        f"Worker status summary:\n{clip_text(json.dumps(worker, indent=2), 3000)}"
    )

    input_items: list[dict[str, Any]] = [
        {"role": "user", "content": user},
    ]
    previous_response_id: str | None = None

    try:
        for _ in range(MAX_TOOL_CALLS + 1):
            response = openai_response(
                input_items,
                instructions=system if previous_response_id is None else None,
                previous_response_id=previous_response_id,
            )
            previous_response_id = response.get("id")
            calls = function_calls(response)
            if not calls:
                state.final = text_from_response(response) or "(No final text returned.)"
                log_path = log_run(state)
                return {
                    "ok": True,
                    "action": "ask_custodian",
                    "run_id": state.run_id,
                    "model": OPENAI_MODEL,
                    "tool_calls": state.tool_calls,
                    "final": state.final,
                    "log_path": str(log_path),
                }

            if len(state.tool_calls) >= MAX_TOOL_CALLS:
                state.error = f"Tool call limit reached ({MAX_TOOL_CALLS})."
                log_path = log_run(state)
                return {
                    "ok": False,
                    "action": "ask_custodian",
                    "run_id": state.run_id,
                    "error": state.error,
                    "tool_calls": state.tool_calls,
                    "log_path": str(log_path),
                }

            tool_outputs: list[dict[str, Any]] = []
            for call in calls:
                try:
                    args = json.loads(call.get("arguments") or "{}")
                except json.JSONDecodeError as error:
                    args = {"action": "", "error": f"Invalid tool JSON: {error}"}
                worker_action, worker_payload = map_tool_action(args, payload)
                result = worker_task(worker_action, worker_payload)
                clipped_result = clip_text(json.dumps(result, indent=2))
                state.tool_calls.append(
                    {
                        "name": call.get("name"),
                        "worker_action": worker_action,
                        "arguments": args,
                        "result": json.loads(clipped_result) if clipped_result.startswith("{") else clipped_result,
                    }
                )
                tool_outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.get("call_id"),
                        "output": clipped_result,
                    }
                )
            input_items = tool_outputs

        state.error = "Unexpected orchestrator loop exit."
        log_path = log_run(state)
        return {
            "ok": False,
            "action": "ask_custodian",
            "run_id": state.run_id,
            "error": state.error,
            "log_path": str(log_path),
        }
    except Exception as error:
        state.error = f"{type(error).__name__}: {error}"
        state.final = traceback.format_exc()
        log_path = log_run(state)
        return {
            "ok": False,
            "action": "ask_custodian",
            "run_id": state.run_id,
            "error": state.error,
            "traceback": clip_text(state.final, 4000),
            "log_path": str(log_path),
        }


class OrchestratorHandler(BaseHTTPRequestHandler):
    server_version = "FrntDESKCustodianOrchestrator/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            json_response(
                self,
                200,
                {
                    "ok": True,
                    "service": "custodian-orchestrator",
                    "model": OPENAI_MODEL,
                    "worker_url": WORKER_URL,
                    "worker": worker_status(),
                },
            )
            return
        json_response(self, 404, {"ok": False, "error": "Unknown endpoint."})

    def do_POST(self) -> None:
        try:
            parsed = urlparse(self.path)
            body = read_json_body(self)
            if parsed.path in {"/ask", "/task"}:
                json_response(self, 200, run_orchestrator(body))
                return
            json_response(self, 404, {"ok": False, "error": "Unknown endpoint."})
        except Exception as error:
            json_response(self, 500, {"ok": False, "error": str(error)})

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"{self.address_string()} - {fmt % args}")


def main() -> None:
    if not WRAPPER_PATH.exists():
        raise SystemExit(f"Missing wrapper: {WRAPPER_PATH}")
    server = ThreadingHTTPServer((BIND_HOST, PORT), OrchestratorHandler)
    print(f"Custodian orchestrator listening on http://{BIND_HOST}:{PORT}")
    print(f"Worker URL: {WORKER_URL}")
    print(f"Model: {OPENAI_MODEL}")
    server.serve_forever()


if __name__ == "__main__":
    main()
