#!/usr/bin/env python3
import json
import os
import re
import shutil
import ssl
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.error import URLError
from urllib.request import Request, urlopen


BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
WRAPPER_PATH = BASE_DIR / "the_custodian_wrapper.md"
WORKSPACES_DIR = BASE_DIR / "workspaces"
ACTIVE_WORKSPACE_PATH = BASE_DIR / "active_workspace.txt"
REPOS_DIR = BASE_DIR / "repos"
SELECTED_REPO_PATH = BASE_DIR / "selected_repo.txt"


def load_env(path: Path) -> dict[str, str]:
    values = {}
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


ENV = load_env(ENV_PATH)
ALLOWED_ROOT = Path(
    ENV.get("CUSTODIAN_ALLOWED_LOCAL_ROOT") or str(BASE_DIR.parent)
).expanduser().resolve()
BIND_HOST = ENV.get("CUSTODIAN_BIND_HOST", "127.0.0.1")
PORT = int(ENV.get("CUSTODIAN_PORT", "8765"))
RG_BIN = shutil.which("rg") or "/Users/shadwell/.vscode/extensions/openai.chatgpt-26.506.31421-darwin-arm64/bin/macos-aarch64/rg"
FRONTDESK_CONTAINERS = [
    "open-webui",
    "n8n-local",
    "local-deep-research",
    "searxng-local",
    "qdrant-local",
    "kokoro-tts",
    "vault-ocr",
    "memgraph-local",
    "memgraph-lab",
    "memgraph-restricted",
    "memgraph-restricted-lab",
    "frontdesk-telegram-bridge",
]


def _validate_repo_path(repo: dict) -> dict:
    repo_path = Path(repo["repo_path"]).expanduser().resolve()
    if repo_path != ALLOWED_ROOT and ALLOWED_ROOT not in repo_path.parents:
        raise ValueError("Repo path is outside the allowed Custodian root.")
    repo["repo_path"] = str(repo_path)
    return repo


def load_repo(repo_id: str | None = None) -> dict:
    if repo_id is None:
        repo_id = SELECTED_REPO_PATH.read_text().strip()
    repo_path = REPOS_DIR / f"{repo_id}.json"
    if not repo_path.exists():
        raise ValueError(f"Repo not found: {repo_id}")
    repo = json.loads(repo_path.read_text())
    repo["id"] = repo.get("id", repo_path.stem)
    return _validate_repo_path(repo)


def find_repo(repo_value: str | None) -> dict:
    value = (repo_value or "").strip()
    if not value:
        return load_repo()
    for repo_path in sorted(REPOS_DIR.glob("*.json")):
        repo = json.loads(repo_path.read_text())
        if value in {repo_path.stem, repo.get("id", ""), repo.get("name", "")}:
            repo["id"] = repo.get("id", repo_path.stem)
            return _validate_repo_path(repo)
    return load_repo()


def selected_root(repo: dict | None = None) -> Path:
    return Path((repo or load_repo())["repo_path"]).resolve()


def safe_path(path_value: str = ".", root: Path | None = None) -> Path:
    root = root or selected_root()
    target = (root / path_value).resolve()
    if target != root and root not in target.parents:
        raise ValueError("Path is outside the allowed Custodian root.")
    return target


def run_command(args: list[str], cwd: Path | None = None) -> dict:
    cwd = cwd or selected_root()
    result = subprocess.run(
        args,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    return {
        "returncode": result.returncode,
        "stdout": result.stdout[-12000:],
        "stderr": result.stderr[-4000:],
    }


def run_command_input(args: list[str], input_text: str, cwd: Path | None = None, timeout: int = 30) -> dict:
    cwd = cwd or selected_root()
    result = subprocess.run(
        args,
        cwd=str(cwd),
        input=input_text,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    return {
        "returncode": result.returncode,
        "stdout": result.stdout[-12000:],
        "stderr": result.stderr[-4000:],
    }


def run_host_command(args: list[str], timeout: int = 30) -> dict:
    result = subprocess.run(
        args,
        cwd=str(selected_root()),
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    return {
        "returncode": result.returncode,
        "stdout": result.stdout[-20000:],
        "stderr": result.stderr[-6000:],
    }


def run_host_command_input(args: list[str], input_text: str, timeout: int = 30) -> dict:
    result = subprocess.run(
        args,
        cwd=str(selected_root()),
        input=input_text,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    return {
        "returncode": result.returncode,
        "stdout": result.stdout[-20000:],
        "stderr": result.stderr[-6000:],
    }


def frontdesk_container_name(value: str) -> str:
    name = value.strip()
    if name not in FRONTDESK_CONTAINERS:
        raise ValueError("Container is not in the FrnT_DESK allowlist.")
    return name


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.skip_depth += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"} and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data):
        if not self.skip_depth:
            text = data.strip()
            if text:
                self.parts.append(text)

    def text(self) -> str:
        return re.sub(r"\n{3,}", "\n\n", "\n".join(self.parts))


def extract_first_url(text: str) -> str:
    match = re.search(r"https?://[^\s<>)\"']+", text)
    return match.group(0).rstrip(".,;:") if match else ""


def extract_path_from_request(request: str) -> str:
    text = request.strip()
    quoted = re.search(r"['\"]([^'\"]+)['\"]", text)
    if quoted:
        return quoted.group(1)
    match = re.search(r"(?:read|open|show|inspect)\s+(?:file\s+)?(.+)$", text, re.I)
    if not match:
        return ""
    path = match.group(1).strip()
    path = re.sub(r"^(the\s+)?(repo\s+)?file\s+", "", path, flags=re.I)
    return path.strip()


def is_ignored_path(path: Path, root: Path) -> bool:
    rel_parts = path.relative_to(root).parts
    ignored = {
        ".git",
        ".env",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "node_modules",
        ".venv",
        "venv",
        "dist",
        "build",
    }
    return any(part in ignored for part in rel_parts)


def tree_lines(root: Path, include_dirs: list[str], max_depth: int = 3) -> list[str]:
    lines: list[str] = []
    for rel_dir in include_dirs:
        start = safe_path(rel_dir, root)
        if not start.exists() or not start.is_dir():
            continue
        lines.append(f"{rel_dir}/")
        for item in sorted(start.rglob("*"), key=lambda p: (len(p.relative_to(start).parts), str(p).lower())):
            if is_ignored_path(item, root):
                continue
            depth = len(item.relative_to(start).parts)
            if depth > max_depth:
                continue
            prefix = "  " * depth
            suffix = "/" if item.is_dir() else ""
            lines.append(f"{prefix}{item.name}{suffix}")
    return lines


def read_key_files(root: Path, paths: list[str], max_chars: int = 3500) -> list[str]:
    sections: list[str] = []
    for rel in paths:
        matches = sorted(root.glob(rel)) if any(ch in rel for ch in "*?[") else [root / rel]
        for path in matches:
            if not path.exists() or not path.is_file() or is_ignored_path(path, root):
                continue
            if path.name == ".env" or path.suffix in {".key", ".pem", ".p12"}:
                continue
            text = path.read_text(errors="replace")[:max_chars]
            sections.append(f"## {path.relative_to(root)}\n\n```text\n{text}\n```")
    return sections


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


SKIP_SUFFIXES = {
    ".7z",
    ".aiff",
    ".bin",
    ".bmp",
    ".bz2",
    ".db",
    ".dmg",
    ".doc",
    ".docx",
    ".DS_Store",
    ".gif",
    ".gguf",
    ".gz",
    ".heic",
    ".icns",
    ".ico",
    ".jpeg",
    ".jpg",
    ".m4a",
    ".mov",
    ".mp3",
    ".mp4",
    ".pages",
    ".pdf",
    ".pem",
    ".png",
    ".p12",
    ".pyc",
    ".sqlite",
    ".sqlite3",
    ".tar",
    ".tiff",
    ".wav",
    ".webp",
    ".xls",
    ".xlsx",
    ".zip",
}


SKIP_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".DS_Store",
}


SKIP_PREFIXES = (
    "gemini-session-",
)


def redact_text(text: str) -> str:
    redacted = text
    for pattern, replacement in SECRET_REDACTIONS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def should_skip_repo_read(path: Path, root: Path, max_file_bytes: int) -> str:
    if is_ignored_path(path, root):
        return "ignored path"
    if path.name in SKIP_NAMES:
        return "local secret or OS artifact"
    if any(path.name.startswith(prefix) for prefix in SKIP_PREFIXES):
        return "generated/import artifact"
    if path.suffix in SKIP_SUFFIXES:
        return "binary or non-text suffix"
    if path.match("searxng/settings.yml"):
        return "live local search config"
    try:
        size = path.stat().st_size
    except OSError:
        return "unreadable stat"
    if size > max_file_bytes:
        return f"larger than {max_file_bytes} bytes"
    try:
        with path.open("rb") as file:
            sample = file.read(4096)
    except OSError:
        return "unreadable"
    if b"\0" in sample:
        return "binary content"
    return ""


FORBIDDEN_WRITE_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".envrc",
}


FORBIDDEN_WRITE_SUFFIXES = {
    ".key",
    ".pem",
    ".p12",
    ".pfx",
}


FORBIDDEN_TERMINAL_PATTERNS = [
    (re.compile(r"\brm\s+-rf\s+/", re.I), "Refusing host-wide destructive removal."),
    (re.compile(r"\bsudo\b", re.I), "Refusing sudo from the Custodian terminal action."),
    (re.compile(r"\bgit\s+reset\s+--hard\b", re.I), "Refusing destructive git reset."),
    (re.compile(r"\bgit\s+clean\s+-[^\s]*[fd]", re.I), "Refusing destructive git clean."),
    (re.compile(r"\bsecurity\s+find-generic-password\b", re.I), "Refusing macOS keychain reads."),
    (re.compile(r"\b(cat|less|more|head|tail|open)\s+([^;&|]*\/)?\.env(\s|$)", re.I), "Refusing direct .env reads."),
    (re.compile(r"\b(cat|less|more|head|tail|open)\s+.*\.(pem|key|p12|pfx)(\s|$)", re.I), "Refusing direct key material reads."),
]


def assert_repo_write_allowed(path: Path, root: Path) -> None:
    rel = path.relative_to(root)
    if any(part in {".git", "__pycache__", "node_modules", ".venv", "venv"} for part in rel.parts):
        raise ValueError("Refusing to write inside ignored/internal repo path.")
    if path.name in FORBIDDEN_WRITE_NAMES or path.suffix in FORBIDDEN_WRITE_SUFFIXES:
        raise ValueError("Refusing to write secret/key material paths.")
    if path.match("searxng/settings.yml"):
        raise ValueError("Refusing to write live local SearXNG config through the repo tool.")


def assert_terminal_command_allowed(command: str) -> None:
    if not command.strip():
        raise ValueError("Missing command.")
    for pattern, message in FORBIDDEN_TERMINAL_PATTERNS:
        if pattern.search(command):
            raise ValueError(message)


def terminal_command_action(root: Path, payload: dict) -> dict:
    command = str(payload.get("command") or "").strip()
    if not command:
        return {"ok": False, "action": "terminal_command", "error": "Missing command."}
    try:
        timeout = int(payload.get("timeout") or 60)
    except (TypeError, ValueError):
        timeout = 60
    timeout = max(1, min(timeout, 300))
    cwd_value = str(payload.get("cwd") or ".").strip() or "."
    cwd = safe_path(cwd_value, root)
    if not cwd.exists() or not cwd.is_dir():
        return {"ok": False, "action": "terminal_command", "error": "cwd is not a directory.", "cwd": cwd_value}
    try:
        assert_terminal_command_allowed(command)
    except ValueError as error:
        return {"ok": False, "action": "terminal_command", "error": str(error), "command": command}
    try:
        result = subprocess.run(
            ["/bin/zsh", "-lc", command],
            cwd=str(cwd),
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        return {
            "ok": result.returncode == 0,
            "action": "terminal_command",
            "command": command,
            "cwd": str(cwd.relative_to(root)),
            "timeout": timeout,
            "returncode": result.returncode,
            "stdout": stdout[-3000:],
            "stderr": stderr[-1500:],
            "stdout_truncated": len(stdout) > 3000,
            "stderr_truncated": len(stderr) > 1500,
        }
    except subprocess.TimeoutExpired as error:
        return {
            "ok": False,
            "action": "terminal_command",
            "command": command,
            "cwd": str(cwd.relative_to(root)),
            "timeout": timeout,
            "error": f"Command timed out after {timeout} seconds.",
            "stdout": (error.stdout or "")[-1500:] if isinstance(error.stdout, str) else "",
            "stderr": (error.stderr or "")[-800:] if isinstance(error.stderr, str) else "",
        }


def write_file_action(root: Path, payload: dict) -> dict:
    path_value = str(payload.get("path") or "").strip()
    content = payload.get("content")
    if not path_value:
        return {"ok": False, "action": "write_file", "error": "Missing path."}
    if content is None:
        return {"ok": False, "action": "write_file", "error": "Missing content."}
    target = safe_path(path_value, root)
    assert_repo_write_allowed(target, root)
    target.parent.mkdir(parents=True, exist_ok=True)
    before_exists = target.exists()
    before_size = target.stat().st_size if before_exists else 0
    text = str(content)
    target.write_text(text)
    return {
        "ok": True,
        "action": "write_file",
        "path": str(target.relative_to(root)),
        "created": not before_exists,
        "before_size": before_size,
        "after_size": target.stat().st_size,
    }


def append_file_action(root: Path, payload: dict) -> dict:
    path_value = str(payload.get("path") or "").strip()
    content = payload.get("content")
    if not path_value:
        return {"ok": False, "action": "append_file", "error": "Missing path."}
    if content is None:
        return {"ok": False, "action": "append_file", "error": "Missing content."}
    target = safe_path(path_value, root)
    assert_repo_write_allowed(target, root)
    target.parent.mkdir(parents=True, exist_ok=True)
    before_exists = target.exists()
    before_size = target.stat().st_size if before_exists else 0
    with target.open("a", encoding="utf-8") as file:
        file.write(str(content))
    return {
        "ok": True,
        "action": "append_file",
        "path": str(target.relative_to(root)),
        "created": not before_exists,
        "before_size": before_size,
        "after_size": target.stat().st_size,
    }


def replace_text_action(root: Path, payload: dict) -> dict:
    path_value = str(payload.get("path") or "").strip()
    old_text = payload.get("old_text")
    new_text = payload.get("new_text")
    if not path_value:
        return {"ok": False, "action": "replace_text", "error": "Missing path."}
    if old_text is None or new_text is None:
        return {"ok": False, "action": "replace_text", "error": "Missing old_text or new_text."}
    target = safe_path(path_value, root)
    assert_repo_write_allowed(target, root)
    if not target.exists() or not target.is_file():
        return {"ok": False, "action": "replace_text", "error": "File not found."}
    text = target.read_text(errors="replace")
    old = str(old_text)
    count = text.count(old)
    if count == 0:
        return {"ok": False, "action": "replace_text", "error": "old_text not found."}
    if payload.get("replace_all"):
        updated = text.replace(old, str(new_text))
        replacements = count
    else:
        updated = text.replace(old, str(new_text), 1)
        replacements = 1
    target.write_text(updated)
    return {
        "ok": True,
        "action": "replace_text",
        "path": str(target.relative_to(root)),
        "replacements": replacements,
        "after_size": target.stat().st_size,
    }


def delete_file_action(root: Path, payload: dict) -> dict:
    path_value = str(payload.get("path") or "").strip()
    if not path_value:
        return {"ok": False, "action": "delete_file", "error": "Missing path."}
    target = safe_path(path_value, root)
    assert_repo_write_allowed(target, root)
    if not target.exists() or not target.is_file():
        return {"ok": False, "action": "delete_file", "error": "File not found."}
    size = target.stat().st_size
    target.unlink()
    return {
        "ok": True,
        "action": "delete_file",
        "path": str(target.relative_to(root)),
        "deleted_size": size,
    }


def patch_paths(patch_text: str) -> set[str]:
    paths: set[str] = set()
    for line in patch_text.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            for item in parts[2:4]:
                if item.startswith(("a/", "b/")):
                    paths.add(item[2:])
        elif line.startswith(("--- ", "+++ ")):
            item = line[4:].strip()
            if item != "/dev/null" and item.startswith(("a/", "b/")):
                paths.add(item[2:])
    return paths


def apply_patch_action(root: Path, payload: dict) -> dict:
    patch_text = str(payload.get("patch") or "")
    if not patch_text.strip():
        return {"ok": False, "action": "apply_patch", "error": "Missing patch."}
    paths = patch_paths(patch_text)
    if not paths:
        return {"ok": False, "action": "apply_patch", "error": "Patch has no repo-relative paths."}
    for rel_path in paths:
        if rel_path.startswith("/") or ".." in Path(rel_path).parts:
            return {"ok": False, "action": "apply_patch", "error": f"Unsafe patch path: {rel_path}"}
        assert_repo_write_allowed(safe_path(rel_path, root), root)
    check = run_command_input(["git", "apply", "--check", "-"], patch_text, cwd=root)
    if check["returncode"] != 0:
        return {"ok": False, "action": "apply_patch", "error": "Patch check failed.", "check": check}
    applied = run_command_input(["git", "apply", "-"], patch_text, cwd=root)
    return {
        "ok": applied["returncode"] == 0,
        "action": "apply_patch",
        "paths": sorted(paths),
        "result": applied,
    }


def iter_repo_read_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        dirnames[:] = [
            name
            for name in dirnames
            if not is_ignored_path(current / name, root)
        ]
        for filename in filenames:
            path = current / filename
            if not is_ignored_path(path, root):
                files.append(path)
    return sorted(files, key=lambda p: str(p.relative_to(root)).lower())


def full_repo_read_review(root: Path, payload: dict) -> dict:
    max_file_bytes = int(payload.get("max_file_bytes") or 1_000_000)
    max_chars_per_file = int(payload.get("max_chars_per_file") or 12000)
    max_total_chars = int(payload.get("max_total_chars") or 260000)

    inventory: list[str] = []
    skipped: list[str] = []
    sections: list[str] = []
    total_chars = 0
    files_read = 0
    files_truncated = 0

    files = iter_repo_read_files(root)

    for path in files:
        rel = str(path.relative_to(root))
        try:
            size = path.stat().st_size
        except OSError:
            size = -1
        skip_reason = should_skip_repo_read(path, root, max_file_bytes)
        if skip_reason:
            skipped.append(f"- {rel} ({skip_reason})")
            inventory.append(f"- skipped {rel} ({size} bytes; {skip_reason})")
            continue

        if total_chars >= max_total_chars:
            skipped.append(f"- {rel} (total review character budget reached)")
            inventory.append(f"- skipped {rel} ({size} bytes; total review character budget reached)")
            continue

        text = path.read_text(errors="replace")
        redacted = redact_text(text)
        chunk = redacted[:max_chars_per_file]
        if len(redacted) > len(chunk):
            files_truncated += 1
            chunk += "\n\n[TRUNCATED: file excerpt limit reached]"

        remaining = max_total_chars - total_chars
        if len(chunk) > remaining:
            chunk = chunk[:remaining] + "\n\n[TRUNCATED: total review character budget reached]"

        sections.append(f"## {rel}\n\n```text\n{chunk}\n```")
        inventory.append(f"- read {rel} ({size} bytes)")
        total_chars += len(chunk)
        files_read += 1

    content = (
        "# FrnT_DESK Full Repo Read Review Input\n\n"
        "## Bounds\n\n"
        f"- max file size read: {max_file_bytes} bytes\n"
        f"- max chars per file: {max_chars_per_file}\n"
        f"- max total chars returned: {max_total_chars}\n"
        "- secrets are redacted before output\n"
        "- binary files, local `.env` files, private keys, live local search config, and generated/import artifacts are skipped\n\n"
        "## Summary\n\n"
        f"- files discovered: {len(files)}\n"
        f"- files read: {files_read}\n"
        f"- files skipped: {len(skipped)}\n"
        f"- file excerpts truncated: {files_truncated}\n\n"
        "## Git status\n\n"
        "```text\n"
        + (run_command(["git", "status", "--short"], cwd=root).get("stdout", "").strip() or "Clean")
        + "\n```\n\n"
        "## File Inventory\n\n"
        "```text\n"
        + "\n".join(inventory[:500])
        + ("\n[TRUNCATED: inventory limit reached]" if len(inventory) > 500 else "")
        + "\n```\n\n"
        "## Skipped Files\n\n"
        + ("\n".join(skipped[:250]) if skipped else "No files skipped.")
        + ("\n- [TRUNCATED: skipped-file list limit reached]" if len(skipped) > 250 else "")
        + "\n\n"
        "## Redacted File Excerpts\n\n"
        + ("\n\n".join(sections) if sections else "No readable text files found within bounds.")
    )
    return {
        "ok": True,
        "action": "full_repo_read_review",
        "content": content,
        "files_discovered": len(files),
        "files_read": files_read,
        "files_skipped": len(skipped),
        "files_truncated": files_truncated,
        "truncated": total_chars >= max_total_chars,
    }


def search_patterns(root: Path, pattern: str, max_chars: int = 8000) -> str:
    result = run_command([RG_BIN, "--line-number", "--no-heading", "--color", "never", "-S", pattern], cwd=root)
    return result.get("stdout", "").strip()[:max_chars]


def secret_pattern_scan(root: Path) -> list[str]:
    patterns = {
        "openai_api_key": r"sk-[A-Za-z0-9_\-]{20,}",
        "generic_api_key_assignment": r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[^'\"\s]{8,}",
        "private_key_block": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        "telegram_bot_token": r"\b\d{8,12}:[A-Za-z0-9_-]{30,}\b",
    }
    findings: list[str] = []
    for name, pattern in patterns.items():
        result = run_command(
            [
                RG_BIN,
                "--line-number",
                "--no-heading",
                "--color",
                "never",
                "-S",
                pattern,
            ],
            cwd=root,
        )
        for line in result.get("stdout", "").splitlines():
            path_line = line.split(":", 2)
            if len(path_line) < 2:
                continue
            rel_path = path_line[0]
            if rel_path.endswith(".env") or "/.env" in rel_path:
                continue
            findings.append(f"- {name}: {rel_path}:{path_line[1]}")
    return findings[:100]


def docker_ps_frontdesk() -> dict:
    return run_host_command(
        ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}\t{{.Ports}}"]
    )


def docker_logs_frontdesk(container: str, tail: int = 120) -> dict:
    name = frontdesk_container_name(container)
    return run_host_command(["docker", "logs", "--tail", str(tail), name])


def container_url_check(container: str, urls: list[str]) -> list[dict]:
    name = frontdesk_container_name(container)
    checks = []
    for url in urls:
        script = (
            "import urllib.request\n"
            f"url={url!r}\n"
            "try:\n"
            "    response=urllib.request.urlopen(url, timeout=5)\n"
            "    print(response.status)\n"
            "except Exception as error:\n"
            "    print(type(error).__name__ + ': ' + str(error))\n"
        )
        result = run_host_command(["docker", "exec", name, "python", "-c", script], timeout=10)
        checks.append(
            {
                "container": name,
                "url": url,
                "ok": result["returncode"] == 0 and result["stdout"].strip().startswith(("2", "3")),
                "stdout": result["stdout"].strip(),
                "stderr": result["stderr"].strip(),
            }
        )
    return checks


def stack_health_check() -> dict:
    checks = container_url_check(
        "local-deep-research",
        [
            "http://host.docker.internal:7476/v1/models",
            "http://host.docker.internal:7474/v1/models",
            "http://host.docker.internal:8081/search?q=test&format=json",
        ],
    )
    log_hints = {
        "local-deep-research": docker_logs_frontdesk("local-deep-research", 80),
        "searxng-local": docker_logs_frontdesk("searxng-local", 80),
    }
    return {
        "ok": True,
        "action": "stack_health_check",
        "containers": docker_ps_frontdesk(),
        "connectivity": checks,
        "logs": log_hints,
    }


def openwebui_theme_check(root: Path) -> dict:
    css_path = root / "gui_colors_frnt_desk.css"
    if not css_path.exists():
        return {
            "ok": False,
            "action": "openwebui_theme_check",
            "error": "Missing gui_colors_frnt_desk.css in selected repo.",
        }

    local_hash = run_host_command(["shasum", "-a", "256", str(css_path)])
    container_hash = run_host_command(["docker", "exec", "open-webui", "sha256sum", "/app/build/static/custom.css"])
    container_tail = run_host_command(["docker", "exec", "open-webui", "tail", "-n", "35", "/app/build/static/custom.css"])
    http_check = run_host_command(["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}", "http://127.0.0.1:3000/static/custom.css"])

    local_sha = (local_hash.get("stdout") or "").split()[0] if local_hash.get("stdout") else ""
    mounted_sha = (container_hash.get("stdout") or "").split()[0] if container_hash.get("stdout") else ""
    return {
        "ok": bool(local_sha and mounted_sha and local_sha == mounted_sha),
        "action": "openwebui_theme_check",
        "local_sha": local_sha,
        "mounted_sha": mounted_sha,
        "mounted_matches_local": bool(local_sha and mounted_sha and local_sha == mounted_sha),
        "http_status": (http_check.get("stdout") or "").strip(),
        "tail": container_tail.get("stdout", "")[-2500:],
        "errors": {
            "local_hash": local_hash.get("stderr", ""),
            "container_hash": container_hash.get("stderr", ""),
            "http_check": http_check.get("stderr", ""),
            "tail": container_tail.get("stderr", ""),
        },
    }


MEMORY_COLLECTION_ALIASES = {
    "assistant_archive": "assistant_chat_history",
    "all_chat_history": "assistant_chat_history",
    "working_memory": "working_memory",
    "current_session_memory": "working_memory",
    "knowledge_base": "personal_knowledge_base",
    "obsidian": "personal_knowledge_base",
    "accords": "ethics_accords_memory",
    "ethics_accords": "ethics_accords_memory",
    "ethics": "ethics_philosophy_memory",
    "ethics_philosophy": "ethics_philosophy_memory",
    "research_sources": "research_source_memory",
    "source_history": "research_source_memory",
}


def memory_search_action(payload: dict) -> dict:
    query = str(payload.get("q") or payload.get("query") or "").strip().lower()
    collection_value = str(payload.get("collection") or "").strip()
    collection = MEMORY_COLLECTION_ALIASES.get(collection_value, collection_value)
    if not query:
        return {"ok": False, "action": "memory_search", "error": "Missing query."}
    if not collection:
        return {
            "ok": False,
            "action": "memory_search",
            "error": "Missing collection.",
            "known_collections": sorted(set(MEMORY_COLLECTION_ALIASES.values())),
        }

    request_payload = json.dumps({"limit": 50, "with_payload": True, "with_vector": False}).encode("utf-8")
    request = Request(
        f"http://127.0.0.1:6333/collections/{collection}/points/scroll",
        data=request_payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as error:
        return {
            "ok": False,
            "action": "memory_search",
            "collection": collection,
            "error": f"Qdrant memory search failed: {error}",
        }

    matches = []
    for point in data.get("result", {}).get("points", []):
        item = point.get("payload", {})
        blob = json.dumps(item, ensure_ascii=False).lower()
        if query in blob:
            matches.append(
                {
                    "id": point.get("id"),
                    "collection": collection,
                    "title": item.get("title"),
                    "source": item.get("source"),
                    "type": item.get("type"),
                    "text": (item.get("text") or item.get("assistant_text") or item.get("user_text") or "")[:1200],
                }
            )
    return {
        "ok": True,
        "action": "memory_search",
        "collection": collection,
        "query": query,
        "mode": "bounded_payload_keyword_scan",
        "matches": matches[:10],
        "scanned_points": len(data.get("result", {}).get("points", [])),
    }


def graph_query_action(payload: dict) -> dict:
    query = str(payload.get("query") or "").strip()
    if not query:
        return {"ok": False, "action": "graph_query", "error": "Missing query."}
    blocked = re.search(r"\b(CREATE|MERGE|SET|DELETE|DETACH|DROP|REMOVE|LOAD\s+CSV)\b", query, re.I)
    if blocked:
        return {
            "ok": False,
            "action": "graph_query",
            "error": "Only read-only Cypher queries are allowed through graph_query.",
        }
    result = run_host_command_input(
        ["docker", "exec", "-i", "memgraph-local", "mgconsole", "-output_format=tabular", "-no_history"],
        query.rstrip(";") + ";\n",
        timeout=30,
    )
    return {
        "ok": result["returncode"] == 0,
        "action": "graph_query",
        "query": query,
        **result,
    }


def repair_deep_research_endpoint() -> dict:
    qwen35 = container_url_check("local-deep-research", ["http://host.docker.internal:7476/v1/models"])[0]
    if not qwen35["ok"]:
        return {
            "ok": False,
            "action": "repair_deep_research_endpoint",
            "error": "Qwen3.5 endpoint on host.docker.internal:7476 is not reachable from local-deep-research.",
            "check": qwen35,
        }

    inspect_result = run_host_command(["docker", "inspect", "local-deep-research"])
    if inspect_result["returncode"] != 0:
        return {
            "ok": False,
            "action": "repair_deep_research_endpoint",
            "error": "Could not inspect local-deep-research before repair.",
            "inspect": inspect_result,
        }
    inspect_data = json.loads(inspect_result["stdout"])[0]
    image = inspect_data["Config"]["Image"]
    mounts = inspect_data.get("Mounts", [])

    backup_name = "local-deep-research-backup"
    existing_backup = run_host_command(["docker", "inspect", backup_name])
    if existing_backup["returncode"] == 0:
        run_host_command(["docker", "rm", "-f", backup_name], timeout=60)

    run_args = [
        "docker",
        "run",
        "-d",
        "--name",
        "local-deep-research",
        "--restart",
        "unless-stopped",
        "-p",
        "127.0.0.1:5000:5000",
    ]
    for mount in mounts:
        destination = mount.get("Destination")
        if not destination:
            continue
        if mount.get("Type") == "volume" and mount.get("Name"):
            run_args.extend(["-v", f"{mount['Name']}:{destination}"])
        elif mount.get("Type") == "bind" and mount.get("Source"):
            run_args.extend(["-v", f"{mount['Source']}:{destination}"])
    run_args.extend(
        [
            "-e",
            "LDR_DATA_DIR=/data",
            "-e",
            "LDR_LLM_LLAMACPP_URL=http://host.docker.internal:7476/v1",
            "-e",
            "LDR_LLM_LLAMACPP_API_KEY=sk-not-needed",
            "-e",
            "LDR_SEARCH_ENGINE_WEB_SEARXNG_DEFAULT_PARAMS_INSTANCE_URL=http://host.docker.internal:8081",
            "-e",
            "LDR_SEARCH_SEARCH_STRATEGY=focused_iteration",
            image,
        ]
    )

    steps = []
    for args in [
        ["docker", "stop", "local-deep-research"],
        ["docker", "rename", "local-deep-research", backup_name],
        run_args,
    ]:
        result = run_host_command(args, timeout=90)
        steps.append({"cmd": " ".join(args[:3]), **result})
        if result["returncode"] != 0:
            return {
                "ok": False,
                "action": "repair_deep_research_endpoint",
                "failed_step": " ".join(args[:3]),
                "steps": steps,
            }

    health = run_host_command(["docker", "inspect", "--format", "{{.State.Health.Status}}", "local-deep-research"])
    return {
        "ok": True,
        "action": "repair_deep_research_endpoint",
        "message": "Recreated local-deep-research with llama.cpp URL set to host.docker.internal:7476/v1 and local-only port binding.",
        "steps": steps,
        "health": health,
        "post_check": stack_health_check(),
    }


def list_repos() -> list[dict]:
    repos = []
    for repo_path in sorted(REPOS_DIR.glob("*.json")):
        repo = json.loads(repo_path.read_text())
        repos.append(
            {
                "id": repo.get("id", repo_path.stem),
                "name": repo.get("name", repo_path.stem),
                "location": repo.get("location", "local"),
                "privacy": repo.get("privacy", ""),
                "repo_path": repo.get("repo_path", ""),
            }
        )
    return repos


def repo_picker_url() -> str:
    return f"http://127.0.0.1:{PORT}/repo-picker"


def register_repo_path(repo_path: Path, name: str | None = None) -> dict:
    target = repo_path.expanduser().resolve()
    if target != ALLOWED_ROOT and ALLOWED_ROOT not in target.parents:
        raise ValueError("Repo path is outside allowed root.")
    if not target.exists() or not target.is_dir():
        raise ValueError("Repo path is not a directory.")
    if not (target / ".git").exists():
        raise ValueError("Selected folder is not a git repo.")

    repo_name = name or target.name
    for existing in list_repos():
        if Path(existing["repo_path"]).expanduser().resolve() == target:
            SELECTED_REPO_PATH.write_text(f"{existing['id']}\n")
            return load_repo(existing["id"])

    repo_id = unique_repo_id(repo_id_from_name(repo_name, str(target)))
    repo = {
        "id": repo_id,
        "name": repo_name,
        "location": "local",
        "repo_path": str(target),
        "privacy": "local-first",
        "allowed_tools": ["list", "read", "search", "git_status", "git_diff", "terminal_command", "write_file", "append_file", "replace_text", "delete_file", "apply_patch"],
        "allowed_models": ["local", "codex-by-approval"],
        "approval_required": ["commit", "docker_restart", "ssh"],
    }
    REPOS_DIR.mkdir(parents=True, exist_ok=True)
    (REPOS_DIR / f"{repo_id}.json").write_text(json.dumps(repo, indent=2) + "\n")
    SELECTED_REPO_PATH.write_text(f"{repo_id}\n")
    return load_repo(repo_id)


def open_native_repo_picker() -> dict:
    script = (
        'POSIX path of (choose folder with prompt '
        '"Choose a git repo folder for The Custodian")'
    )
    result = subprocess.run(
        ["osascript", "-e", script],
        text=True,
        capture_output=True,
        timeout=300,
        check=False,
    )
    if result.returncode != 0:
        return {
            "ok": False,
            "cancelled": True,
            "error": (result.stderr or result.stdout or "Folder picker cancelled.").strip(),
        }
    selected_path = Path(result.stdout.strip())
    repo = register_repo_path(selected_path)
    return {"ok": True, "repo": repo}


def open_web_repo_picker() -> dict:
    try:
        browser_bundle = ENV.get("CUSTODIAN_REPO_PICKER_BROWSER_BUNDLE", "com.brave.Browser").strip()
        command = ["open", "-b", browser_bundle, repo_picker_url()] if browser_bundle else ["open", repo_picker_url()]
        subprocess.run(command, timeout=5, check=False)
        return {"opened": True}
    except Exception as error:
        return {"opened": False, "error": str(error)}


def repo_id_from_name(name: str, path: str) -> str:
    value = name.strip() or Path(path).name
    value = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.lower()).strip("-")
    return value or "repo"


def unique_repo_id(base_id: str) -> str:
    repo_id = base_id
    count = 2
    while (REPOS_DIR / f"{repo_id}.json").exists():
        repo_id = f"{base_id}-{count}"
        count += 1
    return repo_id


def browse_dirs(path_value: str = "") -> dict:
    root = ALLOWED_ROOT
    target = (root / path_value).expanduser().resolve() if path_value else root
    if target != root and root not in target.parents:
        raise ValueError("Browse path is outside the allowed Custodian root.")
    if not target.exists() or not target.is_dir():
        raise ValueError("Browse path is not a directory.")

    dirs = []
    for item in sorted(target.iterdir(), key=lambda p: p.name.lower()):
        if not item.is_dir() or item.name.startswith("."):
            continue
        try:
            rel = str(item.relative_to(root))
        except ValueError:
            continue
        dirs.append(
            {
                "name": item.name,
                "path": rel,
                "is_git_repo": (item / ".git").exists(),
            }
        )

    parent = ""
    if target != root:
        parent = str(target.parent.relative_to(root))
    return {
        "ok": True,
        "allowed_root": str(root),
        "current_path": "" if target == root else str(target.relative_to(root)),
        "parent_path": parent,
        "dirs": dirs,
        "selected_repo": load_repo(),
        "repos": list_repos(),
    }


def load_workspace(workspace_id: str | None = None) -> dict:
    """Backward-compatible alias for older local calls."""
    if workspace_id is None:
        return load_repo()
    return find_repo(workspace_id)


def list_workspaces() -> list[dict]:
    """Backward-compatible alias for older local calls."""
    return list_repos()


def read_json_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0:
        return {}
    raw = handler.rfile.read(length).decode("utf-8")
    return json.loads(raw) if raw else {}


def infer_task_action(request: str, mode: str) -> dict:
    text = f"{mode} {request}".lower()
    request_text = request.strip().lower()
    if request_text == "/repo":
        return {"action": "repo_picker"}
    if any(term in text for term in ["terminal command", "shell command", "run command", "run test", "run tests", "run lint", "run build", "execute command"]):
        return {"action": "terminal_command"}
    if any(term in text for term in ["fix stack", "repair stack", "stack repair", "fix deep research", "fix ldr"]):
        return {"action": "repair_deep_research_endpoint"}
    if any(term in text for term in ["apply patch", "patch file", "patch the repo"]):
        return {"action": "apply_patch"}
    if any(term in text for term in ["replace text", "replace in file"]):
        return {"action": "replace_text"}
    if any(term in text for term in ["append file", "append to file"]):
        return {"action": "append_file"}
    if any(term in text for term in ["write file", "create file", "update file"]):
        return {"action": "write_file"}
    if any(term in text for term in ["delete file", "remove file"]):
        return {"action": "delete_file"}
    if any(term in text for term in ["stack health", "container status", "docker status", "check stack", "stack logs"]):
        return {"action": "stack_health_check"}
    if any(term in text for term in ["theme check", "custom.css", "css bind", "css mount", "openwebui theme", "open webui theme"]):
        return {"action": "openwebui_theme_check"}
    if extract_first_url(request):
        return {"action": "fetch_url"}
    if any(term in text for term in ["full read", "full-read", "read all files", "read everything", "full repo read", "full repository read"]):
        return {"action": "full_repo_read_review"}
    if any(term in text for term in ["deep review", "standard review", "quick review", "security scan", "secret scan", "todo scan", "dependency audit"]):
        return {"action": "deep_repo_review"}
    llm_terms = ["llm", "local model", "model integration", "model selection", "ollama", "llama.cpp", "lm studio", "openai-compatible", "openai compatible", "qwen"]
    if "repo" in text and any(term in text for term in llm_terms):
        return {"action": "llm_integration_scan"}
    if "read" in text and "repo" in text:
        return {"action": "repo_summary"}
    if any(word in text for word in ["read ", "open ", "show file", "inspect file"]):
        return {"action": "read"}
    if mode.strip().lower() == "select" or request_text.startswith(("select repo", "change repo", "switch repo")):
        return {"action": "select_repo"}
    if "repo" in text and ("list" in text or "show" in text or "available" in text):
        return {"action": "list_repos"}
    if "diff" in text:
        return {"action": "git_diff"}
    if "status" in text or "git" in text:
        return {"action": "git_status"}
    if "list" in text or "tree" in text or "files" in text:
        return {"action": "list"}
    if "search" in text or "find" in text:
        return {"action": "search"}
    return {"action": "context"}


def execute_safe_action(action: str, payload: dict) -> dict:
    repo = find_repo(payload.get("repo"))
    root = selected_root(repo)
    if action == "repo_picker":
        native = open_native_repo_picker()
        return {
            "ok": bool(native.get("ok")),
            "action": action,
            "selected_repo": native.get("repo") or load_repo(),
            "url": repo_picker_url(),
            "native_picker": native,
            "message": (
                f"Selected repo: {native['repo']['name']}"
                if native.get("ok")
                else f"Folder picker was cancelled or failed. Fallback repo picker: {repo_picker_url()}"
            ),
        }
    if action == "list_repos":
        return {
            "ok": True,
            "action": action,
            "selected_repo": load_repo(),
            "repos": list_repos(),
        }
    if action == "select_repo":
        selected = find_repo(payload.get("repo"))
        SELECTED_REPO_PATH.write_text(f"{selected['id']}\n")
        return {
            "ok": True,
            "action": action,
            "selected_repo": load_repo(selected["id"]),
            "message": "Selected repo updated.",
        }
    if action == "context":
        return {
            "ok": True,
            "action": action,
            "repo": repo,
            "git_status": run_command(["git", "status", "--short"], cwd=root),
        }
    if action == "repo_summary":
        readme = ""
        for name in ["README.md", "readme.md", "README.txt", "README"]:
            path = root / name
            if path.exists() and path.is_file():
                readme = path.read_text(errors="replace")[:12000]
                break
        items = []
        for item in sorted(root.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if item.name in {".git", "__pycache__"}:
                continue
            items.append({
                "name": item.name,
                "path": str(item.relative_to(root)),
                "type": "dir" if item.is_dir() else "file",
            })
        return {
            "ok": True,
            "action": action,
            "repo": repo,
            "items": items,
            "readme": readme,
            "git_status": run_command(["git", "status", "--short"], cwd=root),
        }
    if action == "llm_integration_scan":
        top_level = []
        for item in sorted(root.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if item.name in {".git", "__pycache__"}:
                continue
            top_level.append(f"- [{'dir' if item.is_dir() else 'file'}] {item.name}")

        patterns = [
            "llama.cpp",
            "7474",
            "7475",
            "7476",
            "Qwen",
            "OPENAI_MODEL",
            "api_base_urls",
            "host.docker.internal",
            "ollama",
            "lmstudio",
            "model",
        ]
        search_sections = []
        for pattern in patterns:
            result = run_command(
                [RG_BIN, "--line-number", "--no-heading", "--color", "never", "-S", pattern],
                cwd=root,
            )
            stdout = result.get("stdout", "").strip()
            if stdout:
                search_sections.append(f"## Matches: {pattern}\n\n```text\n{stdout[:5000]}\n```")

        key_files = []
        for rel in [
            "README.md",
            "MLX_QWEN.txt",
            "deep-research/LOCAL_DEEP_RESEARCH.md",
            "telegram-bridge/.env.example",
            "deep-research/.env.example",
            "register-open-webui-agent-models.py",
            "scripts/ai.frontdesk.qwen35-vision.plist",
        ]:
            path = root / rel
            if path.exists() and path.is_file():
                key_files.append(f"## {rel}\n\n```text\n{path.read_text(errors='replace')[:3000]}\n```")

        content = (
            "# FrnT_DESK LLM Integration Scan\n\n"
            "## Top-level repo layout\n\n"
            + "\n".join(top_level)
            + "\n\n"
            "## Key config/docs excerpts\n\n"
            + "\n\n".join(key_files)
            + "\n\n"
            "## Search findings\n\n"
            + ("\n\n".join(search_sections) or "No LLM integration matches found.")
        )
        return {
            "ok": True,
            "action": action,
            "repo": repo,
            "content": content[:30000],
            "truncated": len(content) > 30000,
            "git_status": run_command(["git", "status", "--short"], cwd=root),
        }
    if action == "deep_repo_review":
        include_dirs = ["custodian", "deep-research", "ocr-service", "scripts", "searxng", "telegram-bridge"]
        key_file_patterns = [
            ".gitignore",
            "docker-compose*.yml",
            "compose*.yml",
            "ocr-service/app.py",
            "ocr-service/requirements.txt",
            "deep-research/LOCAL_DEEP_RESEARCH.md",
            "deep-research/.env.example",
            "scripts/*.plist",
            "scripts/*.sh",
            "telegram-bridge/Dockerfile",
            "telegram-bridge/.env.example",
            "open-webui-*-tool.py",
            "qdrant_memory_tools.py",
            "register-open-webui-*.py",
        ]
        todo_matches = search_patterns(root, r"TODO|FIXME|HACK")
        secret_findings = secret_pattern_scan(root)
        key_sections = read_key_files(root, key_file_patterns)
        content = (
            "# FrnT_DESK Deep Repo Review Input\n\n"
            "## Scope\n\n"
            "Non-destructive inspection only: tree walk, key file reads, TODO/FIXME/HACK scan, redacted secret-pattern scan, and git status.\n\n"
            "## Tree walk, depth 3\n\n"
            "```text\n"
            + ("\n".join(tree_lines(root, include_dirs, max_depth=3)) or "No scoped directories found.")
            + "\n```\n\n"
            "## Git status\n\n"
            "```text\n"
            + (run_command(["git", "status", "--short"], cwd=root).get("stdout", "").strip() or "Clean")
            + "\n```\n\n"
            "## TODO / FIXME / HACK matches\n\n"
            "```text\n"
            + (todo_matches or "No TODO/FIXME/HACK matches found.")
            + "\n```\n\n"
            "## Secret-pattern findings, redacted\n\n"
            + ("\n".join(secret_findings) if secret_findings else "No non-env secret-pattern findings found.")
            + "\n\n"
            "## Key file excerpts\n\n"
            + ("\n\n".join(key_sections) if key_sections else "No key files found.")
        )
        return {
            "ok": True,
            "action": action,
            "repo": repo,
            "content": content[:45000],
            "truncated": len(content) > 45000,
        }
    if action == "full_repo_read_review":
        return {
            "ok": True,
            "action": action,
            "repo": repo,
            **full_repo_read_review(root, payload),
        }
    if action == "stack_health_check":
        return stack_health_check()
    if action == "openwebui_theme_check":
        return openwebui_theme_check(root)
    if action == "memory_search":
        return memory_search_action(payload)
    if action == "graph_query":
        return graph_query_action(payload)
    if action == "docker_logs":
        return {
            "ok": True,
            "action": action,
            "container": frontdesk_container_name(str(payload.get("container", ""))),
            "logs": docker_logs_frontdesk(str(payload.get("container", "")), int(payload.get("tail", 120))),
        }
    if action == "repair_deep_research_endpoint":
        return repair_deep_research_endpoint()
    if action == "terminal_command":
        return terminal_command_action(root, payload)
    if action == "write_file":
        return write_file_action(root, payload)
    if action == "append_file":
        return append_file_action(root, payload)
    if action == "replace_text":
        return replace_text_action(root, payload)
    if action == "delete_file":
        return delete_file_action(root, payload)
    if action == "apply_patch":
        return apply_patch_action(root, payload)
    if action == "list":
        target = safe_path(payload.get("path", "."), root)
        if not target.exists() or not target.is_dir():
            return {"ok": False, "error": "Directory not found.", "action": action}
        items = []
        for item in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if item.name in {".git", "__pycache__"}:
                continue
            items.append({
                "name": item.name,
                "path": str(item.relative_to(root)),
                "type": "dir" if item.is_dir() else "file",
            })
        return {"ok": True, "action": action, "items": items}
    if action == "read":
        path_value = payload.get("path") or extract_path_from_request(str(payload.get("request", "")))
        if not path_value:
            return {"ok": False, "error": "Missing file path.", "action": action}
        target = safe_path(path_value, root)
        if not target.exists() or not target.is_file():
            return {"ok": False, "error": "File not found.", "action": action}
        max_chars = int(payload.get("max_chars", 20000))
        text = target.read_text(errors="replace")[:max_chars]
        return {
            "ok": True,
            "action": action,
            "path": str(target.relative_to(root)),
            "content": text,
            "truncated": target.stat().st_size > len(text.encode("utf-8")),
        }
    if action == "fetch_url":
        url = str(payload.get("url") or extract_first_url(str(payload.get("request", "")))).strip()
        if not url:
            return {"ok": False, "error": "Missing URL.", "action": action}
        req = Request(url, headers={"User-Agent": "FrnT_DESK-Custodian/0.1"})
        tls_verified = True
        try:
            response = urlopen(req, timeout=20)
        except (ssl.SSLError, URLError) as error:
            reason = getattr(error, "reason", error)
            if isinstance(reason, ssl.SSLError) or "CERTIFICATE_VERIFY_FAILED" in str(error):
                tls_verified = False
                response = urlopen(req, timeout=20, context=ssl._create_unverified_context())
            else:
                raise
        with response:
            raw = response.read(800000)
            content_type = response.headers.get("Content-Type", "")
            charset = response.headers.get_content_charset() or "utf-8"
        text = raw.decode(charset, errors="replace")
        if "html" in content_type.lower() or text.lstrip().startswith("<"):
            parser = TextExtractor()
            parser.feed(text)
            text = parser.text()
        return {
            "ok": True,
            "action": action,
            "url": url,
            "tls_verified": tls_verified,
            "content_type": content_type,
            "content": text[:30000],
            "truncated": len(text) > 30000,
        }
    if action == "search":
        pattern = str(payload.get("q") or payload.get("query") or "").strip()
        if not pattern:
            return {"ok": False, "error": "Missing q.", "action": action}
        output = run_command([RG_BIN, "--line-number", "--no-heading", "--color", "never", pattern], cwd=root)
        return {"ok": True, "action": action, "query": pattern, **output}
    if action == "git_status":
        return {"ok": True, "action": action, **run_command(["git", "status", "--short"], cwd=root)}
    if action == "git_diff":
        return {"ok": True, "action": action, **run_command(["git", "diff", "--stat"], cwd=root)}
    return {"ok": False, "error": f"Unsupported safe action: {action}", "action": action}


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def html_response(handler: BaseHTTPRequestHandler, status: int, html: str) -> None:
    body = html.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def render_repo_picker() -> str:
    picker = browse_dirs()
    selected = picker["selected_repo"]
    rows = "\n".join(
        "<tr>"
        f"<td><button data-path='{escape(item['path'])}' class='nav-folder'>Folder</button></td>"
        f"<td class='name'>{escape(item['name'])}</td>"
        f"<td>{'Git repo' if item['is_git_repo'] else 'Folder'}</td>"
        f"<td>{f'<button data-path=\"{escape(item['path'])}\" data-name=\"{escape(item['name'])}\" class=\"select-path\">Select</button>' if item['is_git_repo'] else ''}</td>"
        "</tr>"
        for item in picker["dirs"]
    )
    repo_rows = "\n".join(
        f"<li><button data-repo='{escape(repo['id'])}' class='select-known'>{escape(repo['name'])}</button>"
        f"<code>{escape(repo['repo_path'])}</code></li>"
        for repo in picker["repos"]
    )
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>FrnT_DESK Repo Selector</title>
  <style>
    :root {{ color-scheme: dark; }}
    body {{ background:#17051d; color:#f7ead2; font:15px ui-monospace, SFMono-Regular, Menlo, monospace; margin:0; }}
    header {{ position:sticky; top:0; background:#17051d; border-bottom:1px solid #382340; padding:18px 24px; z-index:2; }}
    main {{ padding:20px 24px 36px; }}
    h1 {{ font-size:24px; margin:0 0 12px; }}
    h2 {{ font-size:18px; margin:28px 0 10px; }}
    code {{ color:#cda45f; }}
    button {{ background:#25102d; color:#f7ead2; border:1px solid #6d4f75; border-radius:6px; padding:8px 10px; margin:0; cursor:pointer; font:inherit; }}
    button:hover {{ border-color:#f0a020; }}
    input {{ width:min(720px,90vw); background:#120f16; color:#f7ead2; border:1px solid #6d4f75; border-radius:6px; padding:9px; font:inherit; }}
    table {{ border-collapse:collapse; width:100%; max-width:1100px; background:#120f16; border:1px solid #382340; }}
    th, td {{ border-bottom:1px solid #382340; padding:9px 10px; text-align:left; vertical-align:middle; }}
    th {{ color:#cda45f; font-weight:600; background:#1d0b25; position:sticky; top:84px; }}
    tr:hover td {{ background:#201027; }}
    .name {{ color:#fff7e8; }}
    .pathbar {{ display:flex; gap:8px; align-items:center; flex-wrap:wrap; }}
    .crumb {{ color:#f0a020; }}
    .muted {{ color:#bca586; }}
    .status {{ color:#9bd38f; min-height:24px; }}
    .select-path, .select-known {{ color:#ffc04d; }}
    .known-row {{ display:grid; grid-template-columns:minmax(180px,260px) 1fr; gap:10px; align-items:center; max-width:1100px; margin:6px 0; }}
  </style>
</head>
<body>
  <header>
    <h1>FrnT_DESK Repo Selector</h1>
    <div class="muted">Selected repo</div>
    <code id="selected">{escape(selected['name'])} — {escape(selected['repo_path'])}</code>
  </header>
  <main>
    <div class="pathbar">
      <button id="home">Home</button>
      <button id="up">Parent Folder</button>
      <span class="muted">Current folder:</span>
      <span class="crumb" id="path"></span>
    </div>

    <h2>Folders</h2>
    <table>
      <thead>
        <tr><th>Open</th><th>Name</th><th>Type</th><th>Action</th></tr>
      </thead>
      <tbody id="dirs">{rows}</tbody>
    </table>

    <h2>Known Repos</h2>
    <div id="known">{repo_rows}</div>

    <h2>Add Current Folder As Repo</h2>
    <input id="repoName" placeholder="Repo display name">
    <button id="add">Add and select current folder</button>

    <p class="status" id="status"></p>
  </main>

  <script>
    let currentPath = "";
    async function api(path, opts) {{
      const res = await fetch(path, opts);
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "Request failed");
      return data;
    }}
    function button(label, cls, attrs) {{
      const b = document.createElement("button");
      b.textContent = label;
      b.className = cls || "";
      for (const [k,v] of Object.entries(attrs || {{}})) b.dataset[k] = v;
      return b;
    }}
    async function load(path="") {{
      const data = await api("/repo/browse?path=" + encodeURIComponent(path));
      currentPath = data.current_path || "";
      document.getElementById("path").textContent = data.allowed_root + (currentPath ? "/" + currentPath : "");
      document.getElementById("selected").textContent = data.selected_repo.name + " — " + data.selected_repo.repo_path;
      const dirs = document.getElementById("dirs");
      dirs.innerHTML = "";
      data.dirs.forEach(item => {{
        const tr = document.createElement("tr");
        const openCell = document.createElement("td");
        const nameCell = document.createElement("td");
        const typeCell = document.createElement("td");
        const actionCell = document.createElement("td");
        const b = button("Folder", "nav-folder", {{path:item.path}});
        b.onclick = () => load(item.path);
        openCell.appendChild(b);
        nameCell.textContent = item.name;
        nameCell.className = "name";
        typeCell.textContent = item.is_git_repo ? "Git repo" : "Folder";
        if (item.is_git_repo) {{
          const s = button("Select", "select-path", {{path:item.path, name:item.name}});
          s.onclick = () => addRepo(item.name, item.path);
          actionCell.appendChild(s);
        }}
        tr.appendChild(openCell);
        tr.appendChild(nameCell);
        tr.appendChild(typeCell);
        tr.appendChild(actionCell);
        dirs.appendChild(tr);
      }});
      const known = document.getElementById("known");
      known.innerHTML = "";
      data.repos.forEach(repo => {{
        const row = document.createElement("div");
        row.className = "known-row";
        const b = button(repo.name, "select-known", {{repo:repo.id}});
        b.onclick = () => selectRepo(repo.id);
        row.appendChild(b);
        const c = document.createElement("code");
        c.textContent = repo.repo_path;
        row.appendChild(c);
        known.appendChild(row);
      }});
    }}
    async function addRepo(name, path) {{
      const displayName = name || document.getElementById("repoName").value || path.split("/").pop() || "Repo";
      const data = await api("/repo/register-select", {{
        method:"POST",
        headers:{{"Content-Type":"application/json"}},
        body:JSON.stringify({{name:displayName, path}})
      }});
      document.getElementById("status").textContent = "Selected " + data.repo.name;
      await load(currentPath);
    }}
    async function selectRepo(repo) {{
      const data = await api("/repo/select", {{
        method:"POST",
        headers:{{"Content-Type":"application/json"}},
        body:JSON.stringify({{repo}})
      }});
      document.getElementById("status").textContent = "Selected " + data.repo.name;
      await load(currentPath);
    }}
    document.getElementById("up").onclick = async () => {{
      const data = await api("/repo/browse?path=" + encodeURIComponent(currentPath));
      await load(data.parent_path || "");
    }};
    document.getElementById("home").onclick = () => load("");
    document.getElementById("add").onclick = () => addRepo(document.getElementById("repoName").value, currentPath);
    load();
  </script>
</body>
</html>"""


class CustodianHandler(BaseHTTPRequestHandler):
    server_version = "FrntDESKCustodian/0.1"

    def do_GET(self) -> None:
        try:
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)

            if parsed.path == "/health":
                json_response(self, 200, {"ok": True, "service": "custodian-worker"})
                return

            if parsed.path == "/repo-picker":
                html_response(self, 200, render_repo_picker())
                return

            if parsed.path == "/repo/browse":
                json_response(self, 200, browse_dirs(query.get("path", [""])[0]))
                return

            if parsed.path == "/status":
                repo = load_repo()
                payload = {
                    "ok": True,
                    "allowed_root": str(ALLOWED_ROOT),
                    "selected_repo": repo,
                    "active_workspace": repo,
                    "wrapper_exists": WRAPPER_PATH.exists(),
                    "env_exists": ENV_PATH.exists(),
                    "has_openai_key": bool(ENV.get("OPENAI_API_KEY")),
                    "model": ENV.get("OPENAI_MODEL", ""),
                    "safe_actions": ["list_repos", "select_repo", "repo_summary", "deep_repo_review", "full_repo_read_review", "llm_integration_scan", "stack_health_check", "openwebui_theme_check", "memory_search", "graph_query", "docker_logs", "repair_deep_research_endpoint", "terminal_command", "write_file", "append_file", "replace_text", "delete_file", "apply_patch", "list", "read", "fetch_url", "search", "git_status", "git_diff"],
                }
                json_response(self, 200, payload)
                return

            if parsed.path == "/repos":
                json_response(
                    self,
                    200,
                    {
                        "ok": True,
                        "selected_repo_id": SELECTED_REPO_PATH.read_text().strip(),
                        "repos": list_repos(),
                    },
                )
                return

            if parsed.path == "/repo/selected":
                json_response(self, 200, {"ok": True, "repo": load_repo()})
                return

            if parsed.path == "/workspaces":
                json_response(
                    self,
                    200,
                    {
                        "ok": True,
                        "active_workspace_id": SELECTED_REPO_PATH.read_text().strip(),
                        "workspaces": list_workspaces(),
                    },
                )
                return

            if parsed.path == "/workspace/active":
                json_response(self, 200, {"ok": True, "workspace": load_repo()})
                return

            if parsed.path == "/list":
                json_response(self, 200, execute_safe_action("list", {"path": query.get("path", ["."])[0]}))
                return

            if parsed.path == "/read":
                json_response(
                    self,
                    200,
                    execute_safe_action(
                        "read",
                        {
                            "path": query.get("path", [""])[0],
                            "max_chars": query.get("max_chars", ["20000"])[0],
                        },
                    ),
                )
                return

            if parsed.path == "/search":
                json_response(self, 200, execute_safe_action("search", {"q": query.get("q", [""])[0]}))
                return

            if parsed.path == "/git/status":
                json_response(self, 200, execute_safe_action("git_status", {}))
                return

            if parsed.path == "/git/diff":
                json_response(self, 200, execute_safe_action("git_diff", {}))
                return

            json_response(self, 404, {"ok": False, "error": "Unknown endpoint."})
        except Exception as error:
            json_response(self, 500, {"ok": False, "error": str(error)})

    def do_POST(self) -> None:
        try:
            parsed = urlparse(self.path)
            body = read_json_body(self)

            if parsed.path == "/repo/select":
                repo_id = str(body.get("repo_id") or body.get("repo") or "").strip()
                if not repo_id:
                    json_response(self, 400, {"ok": False, "error": "Missing repo_id."})
                    return
                repo = find_repo(repo_id)
                SELECTED_REPO_PATH.write_text(f"{repo['id']}\n")
                json_response(self, 200, {"ok": True, "repo": load_repo(repo["id"])})
                return

            if parsed.path == "/repo/register-select":
                rel_path = str(body.get("path") or "").strip()
                name = str(body.get("name") or "").strip()
                target = (ALLOWED_ROOT / rel_path).resolve() if rel_path else ALLOWED_ROOT
                repo = register_repo_path(target, name or None)
                json_response(self, 200, {"ok": True, "repo": repo})
                return

            if parsed.path == "/workspace/select":
                workspace_id = str(body.get("workspace_id", "")).strip()
                if not workspace_id:
                    json_response(self, 400, {"ok": False, "error": "Missing workspace_id."})
                    return
                repo = find_repo(workspace_id)
                SELECTED_REPO_PATH.write_text(f"{repo['id']}\n")
                json_response(self, 200, {"ok": True, "workspace": load_repo(repo["id"])})
                return

            if parsed.path == "/task":
                request = str(body.get("request", "")).strip()
                mode = str(body.get("mode", "ask")).strip()
                requested_action = str(body.get("action", "")).strip()
                action = requested_action or infer_task_action(request, mode)["action"]
                result = execute_safe_action(action, body)
                json_response(
                    self,
                    200,
                    {
                        "ok": True,
                        "request": request,
                        "mode": mode,
                        "selected_action": action,
                        "repo": find_repo(body.get("repo")),
                        "workspace": find_repo(body.get("repo")),
                        "result": result,
                    },
                )
                return
        except Exception as error:
            json_response(self, 500, {"ok": False, "error": str(error)})
            return

        json_response(
            self,
            405,
            {
                "ok": False,
                "error": "Write/actions are not enabled in this first Custodian worker build.",
            },
        )

    def log_message(self, fmt: str, *args) -> None:
        print(f"{self.address_string()} - {fmt % args}")


def main() -> None:
    if not WRAPPER_PATH.exists():
        raise SystemExit(f"Missing wrapper: {WRAPPER_PATH}")
    server = ThreadingHTTPServer((BIND_HOST, PORT), CustodianHandler)
    print(f"custodian-worker listening on http://{BIND_HOST}:{PORT}")
    print(f"allowed root: {ALLOWED_ROOT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
