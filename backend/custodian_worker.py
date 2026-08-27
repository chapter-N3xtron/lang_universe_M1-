#!/usr/bin/env python3
import base64
import binascii
import fnmatch
import hashlib
import hmac
import json
import os
import re
import secrets
import selectors
import shutil
import signal
import ssl
import subprocess
import tempfile
import threading
import time
import zipfile
from datetime import UTC, datetime
from html import escape
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from urllib.error import URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
WRAPPER_PATH = BASE_DIR / "the_custodian_wrapper.md"
WORKSPACES_DIR = BASE_DIR / "workspaces"
ACTIVE_WORKSPACE_PATH = BASE_DIR / "active_workspace.txt"
REPOS_DIR = BASE_DIR / "repos"
SELECTED_REPO_PATH = BASE_DIR / "selected_repo.txt"
OCR_UPLOAD_DIR = (BASE_DIR.parent / "data" / "ocr" / "uploads").resolve()
MAX_OCR_DOCUMENT_BYTES = 25 * 1024 * 1024
MAX_OCR_OUTPUT_BYTES = 25 * 1024 * 1024


def load_env(path: Path) -> dict[str, str]:
    values = {}
    if not path.exists():
        return values
    for raw_line in path.read_text().splitlines():
        if (
            not raw_line.strip()
            or raw_line.lstrip().startswith("#")
            or "=" not in raw_line
        ):
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
_legacy_allowed_root = ENV.get("CUSTODIAN_ALLOWED_LOCAL_ROOT", "").strip()
_configured_allowed_roots = ENV.get("CUSTODIAN_ALLOWED_LOCAL_ROOTS", "").strip()
if _legacy_allowed_root:
    ALLOWED_ROOTS = (Path(_legacy_allowed_root).expanduser().resolve(),)
elif _configured_allowed_roots:
    ALLOWED_ROOTS = tuple(
        Path(value).expanduser().resolve()
        for value in _configured_allowed_roots.split(os.pathsep)
        if value
    )
else:
    ALLOWED_ROOTS = (Path.home().resolve(), Path("/Volumes/Storage").resolve())
if not ALLOWED_ROOTS:
    raise RuntimeError("At least one Custodian allowed root is required.")
ALLOWED_ROOT = ALLOWED_ROOTS[0]
BIND_HOST = ENV.get("CUSTODIAN_BIND_HOST", "127.0.0.1")
PORT = int(ENV.get("CUSTODIAN_PORT", "8765"))
API_TOKEN_FILE = Path(
    ENV.get("CUSTODIAN_API_TOKEN_FILE") or BASE_DIR / ".custodian_api_token"
).expanduser()
_NOTICE_TTL_SECONDS = 300
_NOTICE_LOCK = threading.Lock()
_COMPOSE_ENV_LOCK = threading.Lock()
_PENDING_HOST_FILE_NOTICES: dict[str, tuple[str, str, float]] = {}
RG_BIN = (
    shutil.which("rg")
    or "/Users/shadwell/.vscode/extensions/openai.chatgpt-26.506.31421-darwin-arm64/bin/macos-aarch64/rg"
)


def api_token() -> str:
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


def request_is_authenticated(handler: BaseHTTPRequestHandler) -> bool:
    expected = f"Bearer {api_token()}"
    supplied = handler.headers.get("Authorization", "")
    return hmac.compare_digest(supplied, expected)


def path_is_allowed(path: Path) -> bool:
    roots = (ALLOWED_ROOT, *ALLOWED_ROOTS)
    return any(path == root or root in path.parents for root in roots)


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
    if not path_is_allowed(repo_path):
        raise ValueError("Repo path is outside the allowed Custodian roots.")
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
        if value in {
            repo_path.stem,
            repo.get("id", ""),
            repo.get("name", ""),
            repo.get("repo_path", ""),
        }:
            repo["id"] = repo.get("id", repo_path.stem)
            return _validate_repo_path(repo)
    candidate = Path(value).expanduser()
    if candidate.is_absolute() and candidate.is_dir():
        return _validate_repo_path(
            {
                "id": str(candidate.resolve()),
                "name": candidate.name,
                "repo_path": str(candidate),
            }
        )
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


def run_command_input(
    args: list[str], input_text: str, cwd: Path | None = None, timeout: int = 30
) -> dict:
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
        for item in sorted(
            start.rglob("*"),
            key=lambda p: (len(p.relative_to(start).parts), str(p).lower()),
        ):
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
        matches = (
            sorted(root.glob(rel)) if any(ch in rel for ch in "*?[") else [root / rel]
        )
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


SKIP_PREFIXES = ("gemini-session-",)


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


FORBIDDEN_HOST_READ_PARTS = {
    ".aws",
    ".gnupg",
    ".ssh",
    "keychains",
}


FORBIDDEN_HOST_READ_NAMES = {
    ".netrc",
    ".npmrc",
    ".pypirc",
    "cert9.db",
    "cookies",
    "cookies-journal",
    "credentials",
    "credentials.json",
    "key4.db",
    "login data",
    "login data for account",
    "logins.json",
    "web data",
}


FORBIDDEN_HOST_READ_SUFFIXES = {
    ".key",
    ".p12",
    ".pem",
    ".pfx",
}


FORBIDDEN_TERMINAL_PATTERNS = [
    (re.compile(r"\brm\s+-rf\s+/", re.I), "Refusing host-wide destructive removal."),
    (
        re.compile(r"\bsudo\b", re.I),
        "Refusing sudo from the Custodian terminal action.",
    ),
    (re.compile(r"\bgit\s+reset\s+--hard\b", re.I), "Refusing destructive git reset."),
    (
        re.compile(r"\bgit\s+clean\s+-[^\s]*[fd]", re.I),
        "Refusing destructive git clean.",
    ),
    (
        re.compile(r"\bsecurity\s+find-generic-password\b", re.I),
        "Refusing macOS keychain reads.",
    ),
    (
        re.compile(r"\b(cat|less|more|head|tail|open)\s+([^;&|]*\/)?\.env(\s|$)", re.I),
        "Refusing direct .env reads.",
    ),
    (
        re.compile(
            r"\b(cat|less|more|head|tail|open)\s+.*\.(pem|key|p12|pfx)(\s|$)", re.I
        ),
        "Refusing direct key material reads.",
    ),
]


def assert_repo_write_allowed(path: Path, root: Path) -> None:
    rel = path.relative_to(root)
    if any(
        part in {".git", "__pycache__", "node_modules", ".venv", "venv"}
        for part in rel.parts
    ):
        raise ValueError("Refusing to write inside ignored/internal repo path.")
    if path.name in FORBIDDEN_WRITE_NAMES or path.suffix in FORBIDDEN_WRITE_SUFFIXES:
        raise ValueError("Refusing to write secret/key material paths.")
    if path.match("searxng/settings.yml"):
        raise ValueError(
            "Refusing to write live local SearXNG config through the repo tool."
        )


def assert_terminal_command_allowed(command: str) -> None:
    if not command.strip():
        raise ValueError("Missing command.")
    for pattern, message in FORBIDDEN_TERMINAL_PATTERNS:
        if pattern.search(command):
            raise ValueError(message)


SENSITIVE_PARTS = {
    ".git",
    ".ssh",
    ".aws",
    ".gnupg",
    ".docker",
    ".kube",
    ".azure",
    "keychains",
    "credentials",
}
SENSITIVE_NAMES = {
    ".netrc",
    ".npmrc",
    ".pypirc",
    "cookies",
    "credentials.json",
    "login data",
    "logins.json",
}
SENSITIVE_SUFFIXES = {".key", ".pem", ".p12", ".pfx"}
_GLOBAL_SENSITIVE_PATH_REGEX = (
    r".*[/]([.]env[^/]*|[.]ssh|[.]aws|[.]gnupg|[.]docker|[.]kube|[.]azure|"
    r"[Kk]eychains|[Cc]redentials|[.]netrc|[.]npmrc|[.]pypirc|[Cc]ookies|"
    r"[Cc]redentials[.]json|[Ll]ogin [Dd]ata|[Ll]ogins[.]json)([/].*|$)|"
    r".*[.]([Kk][Ee][Yy]|[Pp][Ee][Mm]|[Pp]12|[Pp][Ff][Xx])$"
)
MAX_TEXT_OUTPUT = 100_000
GITHUB_OWNER = ENV.get("CUSTODIAN_GITHUB_OWNER", "chapter-N3xtron").strip()
_GITHUB_REPOSITORY_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
COMMAND_ALLOWLIST = {
    "cargo",
    "go",
    "make",
    "node",
    "npm",
    "pnpm",
    "pytest",
    "python",
    "python3",
    "ruff",
    "uv",
    "yarn",
}
GIT_SUBCOMMANDS = {
    "add",
    "branch",
    "checkout",
    "commit",
    "diff",
    "log",
    "merge",
    "restore",
    "rev-parse",
    "show",
    "status",
    "switch",
}
COMPOSE_READ_SUBCOMMANDS = {"config", "logs", "ps"}
COMPOSE_CHANGE_SUBCOMMANDS = {
    "build",
    "down",
    "pull",
    "restart",
    "start",
    "stop",
    "up",
}


def sanitize_text_outputs(value):
    """Redact every string crossing the HTTP/action boundary."""

    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [sanitize_text_outputs(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_text_outputs(item) for item in value]
    if isinstance(value, dict):
        return {key: sanitize_text_outputs(item) for key, item in value.items()}
    return value


def assert_not_sensitive(target: Path, root: Path | None = None) -> None:
    """Apply one sensitive-path policy to reads, walks, searches, and mutations."""

    parts = target.relative_to(root).parts if root is not None else target.parts
    lowered = [part.casefold() for part in parts]
    name = target.name.casefold()
    if (
        any(part in SENSITIVE_PARTS or part.startswith(".env") for part in lowered)
        or name in SENSITIVE_NAMES
        or target.suffix.casefold() in SENSITIVE_SUFFIXES
    ):
        raise ValueError("Refusing credential or sensitive path.")


def bind_agent_workspace(payload: dict) -> tuple[dict, Path]:
    """Bind an agent action to the exact explicit selected host directory."""

    value = str(payload.get("repo") or "").strip()
    if not value:
        raise ValueError("An exact selected repository is required.")
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        raise ValueError("Selected repository must be an absolute host path.")
    try:
        root = candidate.resolve(strict=True)
    except OSError as exc:
        raise ValueError(
            "Selected repository does not exist on the Custodian host."
        ) from exc
    if not root.is_dir() or not path_is_allowed(root):
        raise ValueError("Selected repository is outside the allowed Custodian roots.")
    # Do not accept aliases, IDs, a stale picker selection, or a canonicalization change.
    if str(root) != value:
        raise ValueError("Selected repository must use its exact canonical host path.")
    return {"id": value, "name": root.name, "repo_path": value}, root


def virtual_path(root: Path, value: object, *, must_exist: bool = False) -> Path:
    raw = str(value or "")
    if not raw.startswith("/"):
        raise ValueError("Filesystem paths must be absolute virtual paths.")
    target = (root / raw.lstrip("/")).resolve(strict=must_exist)
    if target != root and root not in target.parents:
        raise ValueError("Path is outside the selected repository.")
    assert_not_sensitive(target, root)
    return target


def file_info(path: Path, root: Path) -> dict:
    stat = path.stat()
    virtual = "/" + str(path.relative_to(root))
    return {
        "path": virtual,
        "is_dir": path.is_dir(),
        "size": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
    }


def path_revision(path: Path) -> str:
    if not path.exists() and not path.is_symlink():
        return "missing"
    stat = path.lstat()
    digest = hashlib.sha256()
    digest.update(f"{stat.st_mode}:{stat.st_size}:{stat.st_mtime_ns}".encode())
    if path.is_file():
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    elif path.is_dir():
        for item in sorted(path.rglob("*"), key=lambda value: str(value)):
            assert_not_sensitive(item, path)
            item_stat = item.lstat()
            digest.update(str(item.relative_to(path)).encode())
            digest.update(
                f"{item_stat.st_mode}:{item_stat.st_size}:{item_stat.st_mtime_ns}".encode()
            )
    return digest.hexdigest()


def require_revision(path: Path, payload: dict) -> None:
    expected = payload.get("expected_revision")
    if not isinstance(expected, str) or not expected:
        raise ValueError("expected_revision is required for this mutation.")
    if path_revision(path) != expected:
        raise ValueError("Revision conflict; refresh the file before mutating it.")


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".custodian-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".custodian-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def stage_ocr_document_action(root: Path, payload: dict) -> dict:
    source = virtual_path(root, payload.get("path"), must_exist=True)
    if not source.is_file():
        raise ValueError("OCR document was not found.")
    if source.suffix.casefold() != ".pdf":
        raise ValueError("OCR staging currently accepts PDF files only.")
    size = source.stat().st_size
    if size > MAX_OCR_DOCUMENT_BYTES:
        raise ValueError("OCR document exceeds the 25 MB limit.")

    OCR_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    upload_root = OCR_UPLOAD_DIR.resolve(strict=True)
    if upload_root != OCR_UPLOAD_DIR:
        raise ValueError("OCR upload directory is unavailable.")
    target = upload_root / f"{secrets.token_hex(16)}-{source.name}"
    descriptor, temporary = tempfile.mkstemp(prefix=".custodian-ocr-", dir=upload_root)
    try:
        with (
            source.open("rb") as input_stream,
            os.fdopen(descriptor, "wb") as output_stream,
        ):
            shutil.copyfileobj(input_stream, output_stream, length=1024 * 1024)
            output_stream.flush()
            os.fsync(output_stream.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {
        "ok": True,
        "action": "stage_ocr_document",
        "reference": f"upload:{target.name}",
        "filename": source.name,
        "size": size,
    }


def write_ocr_output_action(root: Path, payload: dict) -> dict:
    source = virtual_path(root, payload.get("path"), must_exist=True)
    if not source.is_file() or source.suffix.casefold() != ".pdf":
        raise ValueError("OCR output requires a source PDF in the selected repository.")
    output_format = str(payload.get("output_format") or "")
    if output_format not in {"markdown", "json", "structured", "docx"}:
        raise ValueError(
            "OCR output format must be markdown, json, structured, or docx."
        )

    if output_format == "docx":
        encoded = payload.get("content_base64")
        if not isinstance(encoded, str) or not encoded:
            raise ValueError("DOCX output requires base64-encoded content.")
        try:
            binary_content = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("DOCX output is not valid base64.") from exc
        size = len(binary_content)
        if size > MAX_OCR_OUTPUT_BYTES:
            raise ValueError("OCR output exceeds the 25 MB limit.")
        try:
            with zipfile.ZipFile(BytesIO(binary_content)) as archive:
                names = set(archive.namelist())
        except zipfile.BadZipFile as exc:
            raise ValueError("DOCX output is not a valid Office document.") from exc
        if not {"[Content_Types].xml", "word/document.xml"} <= names:
            raise ValueError("DOCX output is missing required Office document parts.")
        suffix = ".docx"
    else:
        content = payload.get("content")
        if not isinstance(content, str):
            raise ValueError("Text OCR output requires string content.")
        binary_content = None
        size = len(content.encode("utf-8"))
        if size > MAX_OCR_OUTPUT_BYTES:
            raise ValueError("OCR output exceeds the 25 MB limit.")
        suffix = ".json" if output_format in {"json", "structured"} else ".md"

    target = source.with_name(f"{source.stem}.ocr{suffix}")
    assert_repo_write_allowed(target, root)
    replaced = target.exists() or target.is_symlink()
    if replaced and not target.is_file():
        raise ValueError("OCR output path is not a regular file.")
    if binary_content is None:
        atomic_write(target, content)
    else:
        atomic_write_bytes(target, binary_content)
    return {
        "ok": True,
        "action": "write_ocr_output",
        "path": f"/{target.relative_to(root).as_posix()}",
        "size": size,
        "replaced": replaced,
    }


def fs_action(action: str, root: Path, payload: dict) -> dict:
    path = virtual_path(root, payload.get("path", "/"))
    if action == "fs_revision":
        return {"ok": True, "action": action, "revision": path_revision(path)}
    if action == "fs_ls":
        if not path.is_dir():
            raise ValueError("Directory not found.")
        entries = []
        for item in sorted(path.iterdir(), key=lambda item: item.name.casefold()):
            try:
                assert_not_sensitive(item, root)
            except ValueError:
                continue
            entries.append(file_info(item, root))
        return {"ok": True, "action": action, "entries": entries}
    if action == "fs_read":
        if not path.is_file():
            raise ValueError("File not found.")
        offset = max(0, int(payload.get("offset", 0)))
        limit = max(1, min(int(payload.get("limit", 2000)), 5000))
        raw = path.read_bytes()
        if b"\0" in raw[:4096]:
            raise ValueError("Binary files are not supported by repository reads.")
        lines = raw.decode("utf-8", errors="replace").splitlines(keepends=True)
        window = lines[offset : offset + limit]
        result = {
            "ok": True,
            "action": action,
            "file_data": {"content": "".join(window), "encoding": "utf-8"},
            "revision": path_revision(path),
        }
        if window:
            result.update(
                {
                    "start_line": offset + 1,
                    "end_line": offset + len(window),
                    "total_lines": len(lines),
                    "next_offset": offset + len(window),
                }
            )
        return result
    if action in {"fs_glob", "fs_grep"}:
        base = path
        if not base.is_dir():
            raise ValueError("Search path is not a directory.")
        pattern = str(payload.get("pattern") or "")
        if not pattern:
            raise ValueError("A pattern is required.")
        cap_value = payload.get("max_count")
        cap = 1000 if cap_value is None else max(1, min(int(cap_value), 1000))
        matches = []
        candidates = sorted(base.rglob("*"), key=lambda item: str(item).casefold())
        for item in candidates:
            try:
                assert_not_sensitive(item, root)
            except ValueError:
                continue
            rel_base = str(item.relative_to(base))
            file_glob = payload.get("glob")
            if action == "fs_glob":
                if fnmatch.fnmatch(rel_base, pattern) or fnmatch.fnmatch(
                    item.name, pattern
                ):
                    matches.append(file_info(item, root))
            elif item.is_file() and (
                not file_glob
                or fnmatch.fnmatch(rel_base, str(file_glob))
                or fnmatch.fnmatch(item.name, str(file_glob))
            ):
                try:
                    lines = item.read_text(errors="replace").splitlines()
                except OSError:
                    continue
                for number, line in enumerate(lines, 1):
                    if pattern in line:
                        matches.append(
                            {
                                "path": "/" + str(item.relative_to(root)),
                                "line": number,
                                "text": line,
                            }
                        )
                        if len(matches) > cap:
                            return {
                                "ok": True,
                                "action": action,
                                "matches": matches[:cap],
                                "truncated": True,
                            }
            if len(matches) > cap:
                return {
                    "ok": True,
                    "action": action,
                    "matches": matches[:cap],
                    "truncated": True,
                }
        return {"ok": True, "action": action, "matches": matches, "truncated": False}
    if action == "fs_write":
        require_revision(path, payload)
        content = payload.get("content")
        if not isinstance(content, str):
            raise ValueError("content must be text.")
        atomic_write(path, content)
        return {
            "ok": True,
            "action": action,
            "path": str(payload["path"]),
            "revision": path_revision(path),
        }
    if action == "fs_edit":
        require_revision(path, payload)
        if not path.is_file():
            raise ValueError("File not found.")
        old = payload.get("old_string")
        new = payload.get("new_string")
        if not isinstance(old, str) or not isinstance(new, str) or old == new:
            raise ValueError("old_string and distinct new_string are required.")
        text = path.read_text()
        count = text.count(old)
        replace_all = payload.get("replace_all") is True
        if count == 0 or (count > 1 and not replace_all):
            raise ValueError(
                "old_string must match exactly once unless replace_all is true."
            )
        occurrences = count if replace_all else 1
        atomic_write(path, text.replace(old, new, -1 if replace_all else 1))
        return {
            "ok": True,
            "action": action,
            "path": str(payload["path"]),
            "occurrences": occurrences,
            "revision": path_revision(path),
        }
    if action == "fs_delete":
        require_revision(path, payload)
        if path == root:
            raise ValueError("Refusing to delete the selected repository root.")
        if not path.exists() and not path.is_symlink():
            raise ValueError("Path not found.")
        if path.is_dir() and not path.is_symlink() and any(path.iterdir()):
            raise ValueError("Refusing recursive deletion; directory is not empty.")
        temporary = path.with_name(f".custodian-delete-{os.getpid()}-{path.name}")
        os.replace(path, temporary)
        if temporary.is_dir() and not temporary.is_symlink():
            temporary.rmdir()
        else:
            temporary.unlink()
        return {"ok": True, "action": action, "path": str(payload["path"])}
    raise ValueError("Unsupported filesystem action.")


def sanitized_environment() -> dict[str, str]:
    home = BASE_DIR / "data" / "command-home"
    home.mkdir(parents=True, exist_ok=True)
    return {
        "COMPOSE_DISABLE_ENV_FILE": "true",
        "DOCKER_CONFIG": "/Applications/Docker.app/Contents/Resources",
        "HOME": str(home),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
        "TMPDIR": tempfile.gettempdir(),
    }


def broker_environment() -> dict[str, str]:
    environment = sanitized_environment()
    environment["HOME"] = str(Path.home())
    ssh_auth_socket = os.getenv("SSH_AUTH_SOCK", "").strip()
    if ssh_auth_socket:
        environment["SSH_AUTH_SOCK"] = ssh_auth_socket
    return environment


def run_broker_argv(argv: list[str], *, cwd: Path, timeout: int = 300) -> dict:
    executable = shutil.which(argv[0], path=broker_environment()["PATH"])
    if not executable:
        return {"returncode": 127, "output": f"{argv[0]} is unavailable."}
    result = subprocess.run(
        [executable, *argv[1:]],
        cwd=cwd,
        env=broker_environment(),
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    output = f"{result.stdout}{result.stderr}"[-MAX_TEXT_OUTPUT:]
    return {"returncode": result.returncode, "output": redact_text(output)}


def _sandbox_string(value: Path) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def _existing_sensitive_repo_paths(root: Path) -> list[Path]:
    sensitive: list[Path] = []
    for current, dirnames, filenames in os.walk(root):
        current_path = Path(current)
        kept_directories = []
        for dirname in dirnames:
            candidate = current_path / dirname
            try:
                assert_not_sensitive(candidate, root)
            except ValueError:
                sensitive.append(candidate)
            else:
                kept_directories.append(dirname)
        dirnames[:] = kept_directories
        for filename in filenames:
            candidate = current_path / filename
            try:
                assert_not_sensitive(candidate, root)
            except ValueError:
                sensitive.append(candidate)
    return sensitive


def linked_worktree_git_paths(root: Path) -> list[Path]:
    dotgit = root / ".git"
    if not dotgit.is_file():
        return []
    try:
        marker, raw_gitdir = dotgit.read_text(encoding="utf-8").strip().split(":", 1)
        if marker.casefold() != "gitdir":
            return []
        gitdir_value = Path(raw_gitdir.strip()).expanduser()
        gitdir = (
            gitdir_value.resolve()
            if gitdir_value.is_absolute()
            else (root / gitdir_value).resolve()
        )
        common_value = Path((gitdir / "commondir").read_text().strip())
        common = (
            common_value.resolve()
            if common_value.is_absolute()
            else (gitdir / common_value).resolve()
        )
        backlink_value = Path((gitdir / "gitdir").read_text().strip()).expanduser()
        backlink = (
            backlink_value.resolve()
            if backlink_value.is_absolute()
            else (gitdir / backlink_value).resolve()
        )
    except (OSError, ValueError):
        return []
    if (
        common.name != ".git"
        or gitdir.parent != common / "worktrees"
        or backlink != dotgit.resolve()
    ):
        return []
    return [gitdir, common]


def sandboxed_argv(
    root: Path,
    argv: list[str],
    *,
    allow_git_internal: bool = False,
    additional_roots: tuple[Path, ...] = (),
    additional_read_roots: tuple[Path, ...] = (),
    sensitive_read_paths: tuple[Path, ...] = (),
    unrestricted_host_access: bool = False,
) -> list[str]:
    sandbox = Path("/usr/bin/sandbox-exec")
    if not sandbox.is_file():
        raise RuntimeError("Native command containment is unavailable.")
    command_home = Path(sanitized_environment()["HOME"]).resolve()
    exceptions = list(dict.fromkeys((root, command_home, *additional_roots)))
    if allow_git_internal:
        exceptions.extend(linked_worktree_git_paths(root))
    write_exception_rules = " ".join(
        f'(require-not (subpath "{_sandbox_string(path)}"))' for path in exceptions
    )
    read_exception_rules = " ".join(
        f'(require-not (subpath "{_sandbox_string(path)}"))'
        for path in dict.fromkeys((*exceptions, *additional_read_roots))
    )
    rules = ["(version 1)", "(allow default)"]
    if unrestricted_host_access:
        rules.append(
            f'(deny file-read* file-write* (regex #"{_GLOBAL_SENSITIVE_PATH_REGEX}"))'
        )
    else:
        rules.extend(
            [
                f'(deny file-read-data (require-all (subpath "/Users") {read_exception_rules}))',
                f'(deny file-read-data (require-all (subpath "/Volumes") {read_exception_rules}))',
                f'(deny file-write* (require-all (subpath "/Users") {write_exception_rules}))',
                f'(deny file-write* (require-all (subpath "/Volumes") {write_exception_rules}))',
            ]
        )
    read_only_sensitive_paths = {
        path.resolve(strict=False) for path in sensitive_read_paths
    }
    for scope in dict.fromkeys((root, *additional_roots)):
        for sensitive_path in _existing_sensitive_repo_paths(scope):
            if allow_git_internal and sensitive_path == root / ".git":
                continue
            path_text = _sandbox_string(sensitive_path)
            if sensitive_path.resolve(strict=False) in read_only_sensitive_paths:
                rules.append(f'(deny file-write* (subpath "{path_text}"))')
            else:
                rules.append(f'(deny file-read* file-write* (subpath "{path_text}"))')
    return [str(sandbox), "-p", " ".join(rules), *argv]


def bounded_argv(
    root: Path,
    argv: object,
    timeout_value: object = 60,
    *,
    allow_git_internal: bool = False,
    cwd: Path | None = None,
    additional_roots: tuple[Path, ...] = (),
    additional_read_roots: tuple[Path, ...] = (),
    sensitive_read_paths: tuple[Path, ...] = (),
    environment_overrides: dict[str, str] | None = None,
    redacted_values: tuple[str, ...] = (),
    unrestricted_host_access: bool = False,
) -> dict:
    if (
        not isinstance(argv, list)
        or not argv
        or not all(isinstance(item, str) and item for item in argv)
    ):
        raise ValueError("argv must be a non-empty array of strings.")
    if len(argv) > 128 or any(len(item) > 4096 for item in argv):
        raise ValueError("argv exceeds the command bounds.")
    timeout = max(1, min(int(timeout_value), 300))
    working_directory = cwd or root
    command_environment = sanitized_environment()
    command_environment.update(environment_overrides or {})
    process = subprocess.Popen(
        sandboxed_argv(
            root,
            argv,
            allow_git_internal=allow_git_internal,
            additional_roots=additional_roots,
            additional_read_roots=additional_read_roots,
            sensitive_read_paths=sensitive_read_paths,
            unrestricted_host_access=unrestricted_host_access,
        ),
        cwd=working_directory,
        env=command_environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    if process.stdout is None:
        raise RuntimeError("Command output pipe was not created.")
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    deadline = time.monotonic() + timeout
    chunks: list[bytes] = []
    size = 0
    error = ""
    while selector.get_map():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            error = f"Command timed out after {timeout} seconds."
            break
        events = selector.select(min(remaining, 0.25))
        if not events and process.poll() is not None:
            events = [(selector.get_key(process.stdout), selectors.EVENT_READ)]
        for key, _mask in events:
            chunk = os.read(key.fd, 8192)
            if not chunk:
                selector.unregister(key.fileobj)
                continue
            chunks.append(chunk)
            size += len(chunk)
            if size > MAX_TEXT_OUTPUT:
                error = f"Command exceeded the {MAX_TEXT_OUTPUT}-byte output limit."
                break
        if error:
            break
    if error:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=2)
    else:
        process.wait(timeout=2)
    selector.close()
    output = b"".join(chunks)[:MAX_TEXT_OUTPUT].decode("utf-8", errors="replace")
    for value in sorted(set(redacted_values), key=len, reverse=True):
        if value:
            output = output.replace(value, "[REDACTED]")
    return {
        "ok": not error and process.returncode == 0,
        "error": error or None,
        "exit_code": None if error else process.returncode,
        "output": output,
        "truncated": bool(error and size > MAX_TEXT_OUTPUT),
    }


def execute_action(root: Path, payload: dict) -> dict:
    command = payload.get("command")
    if not isinstance(command, str) or not command.strip():
        raise ValueError("command must be a non-empty string.")
    if len(command) > 20_000 or "\0" in command:
        raise ValueError("command exceeds the execution bounds.")
    assert_terminal_command_allowed(command)

    environment = sanitized_environment()
    environment["PATH"] = os.pathsep.join(
        (
            str(root / ".venv" / "bin"),
            str(root / "node_modules" / ".bin"),
            environment["PATH"],
        )
    )
    result = bounded_argv(
        root,
        ["/bin/zsh", "-lc", command],
        payload.get("timeout", 120),
        allow_git_internal=True,
        environment_overrides={"PATH": environment["PATH"]},
        unrestricted_host_access=True,
    )
    return {"action": "execute", **result}


def compose_prepare_environment_action(root: Path, payload: dict) -> dict:
    raw_compose_file = str(payload.get("compose_file") or "").strip()
    if not raw_compose_file or Path(raw_compose_file).is_absolute():
        raise ValueError("Compose file must be a repository-relative path.")
    try:
        compose_file = (root / raw_compose_file).resolve(strict=True)
    except OSError as exc:
        raise ValueError("Compose file does not exist.") from exc
    if compose_file != root and root not in compose_file.parents:
        raise ValueError("Compose file is outside the selected repository.")
    assert_not_sensitive(compose_file, root)
    if (
        not compose_file.is_file()
        or compose_file.suffix.casefold() not in {".yaml", ".yml"}
        or "compose" not in compose_file.name.casefold()
    ):
        raise ValueError("A Docker Compose YAML file is required.")
    if compose_file.stat().st_size > 1_000_000:
        raise ValueError("Compose file exceeds the preparation limit.")

    compose_text = compose_file.read_text(encoding="utf-8")
    required_variables = sorted(
        set(
            re.findall(
                r"\$\{([A-Za-z_][A-Za-z0-9_]*)\:\?[^}]*\}",
                compose_text,
            )
        )
    )
    if not required_variables:
        raise ValueError("Compose file has no explicitly required local variables.")

    environment_file = compose_file.parent / ".env"
    if environment_file.is_symlink():
        raise ValueError("Refusing a symbolic-link Compose environment file.")
    ignored = run_broker_argv(
        ["git", "check-ignore", "--quiet", "--", str(environment_file.relative_to(root))],
        cwd=root,
        timeout=30,
    )
    if ignored["returncode"] != 0:
        raise ValueError("Compose environment file must be ignored by Git.")

    with _COMPOSE_ENV_LOCK:
        if environment_file.is_symlink():
            raise ValueError("Refusing a symbolic-link Compose environment file.")
        existing_text = ""
        if environment_file.exists():
            if not environment_file.is_file() or environment_file.stat().st_size > 100_000:
                raise ValueError("Compose environment file is invalid or too large.")
            existing_text = environment_file.read_text(encoding="utf-8")
        existing_variables = set(
            re.findall(
                r"(?m)^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=",
                existing_text,
            )
        )
        missing_variables = [
            name for name in required_variables if name not in existing_variables
        ]
        if missing_variables:
            content = existing_text
            if content and not content.endswith("\n"):
                content += "\n"
            content += "".join(
                f"{name}={secrets.token_urlsafe(32)}\n"
                for name in missing_variables
            )
            atomic_write(environment_file, content)
        if environment_file.exists():
            environment_file.chmod(0o600)

    return {
        "ok": True,
        "action": "compose_prepare_environment",
        "generated": len(missing_variables),
        "required": len(required_variables),
        "values_exposed": False,
    }


def host_command_action(root: Path, payload: dict) -> dict:
    argv = payload.get("argv")
    if (
        not isinstance(argv, list)
        or not argv
        or not all(isinstance(item, str) and item for item in argv)
    ):
        raise ValueError("argv must be a non-empty array of strings.")

    cwd_value = str(payload.get("cwd") or "").strip()
    candidate = Path(cwd_value).expanduser()
    if not candidate.is_absolute():
        raise ValueError("Host command cwd must be an absolute path.")
    try:
        cwd = candidate.resolve(strict=True)
    except OSError as exc:
        raise ValueError("Host command cwd does not exist.") from exc
    if not cwd.is_dir():
        raise ValueError("Host command cwd must be a directory.")
    assert_not_sensitive(cwd)

    executable_name = Path(argv[0]).name
    if executable_name in {
        "bash",
        "dash",
        "doas",
        "fish",
        "security",
        "sh",
        "su",
        "sudo",
        "zsh",
    }:
        raise ValueError("Privileged, shell, and keychain executables are not allowed.")
    if "/" in argv[0] or argv[0].startswith("."):
        executable_candidate = Path(argv[0]).expanduser()
        unresolved_executable = (
            executable_candidate
            if executable_candidate.is_absolute()
            else cwd / executable_candidate
        )
        try:
            executable = unresolved_executable.parent.resolve(strict=True) / unresolved_executable.name
            executable_target = executable.resolve(strict=True)
        except OSError as exc:
            raise ValueError("Host command executable does not exist.") from exc
        if executable != cwd and cwd not in executable.parents:
            raise ValueError("Host command executable must remain inside cwd.")
        assert_not_sensitive(executable)
        assert_not_sensitive(executable_target)
        if Path(executable_target).name in {
            "bash",
            "dash",
            "doas",
            "fish",
            "security",
            "sh",
            "su",
            "sudo",
            "zsh",
        }:
            raise ValueError("Privileged, shell, and keychain executables are not allowed.")
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise ValueError("Host command executable is not executable.")
        assert_terminal_command_allowed(" ".join([str(executable_target), *argv[1:]]))
        argv = [str(executable), *argv[1:]]
    assert_terminal_command_allowed(" ".join(argv))

    for argument in argv:
        lowered = argument.casefold()
        if (
            any(
                marker in lowered
                for marker in (".env", ".ssh", ".aws", "keychain", "credential")
            )
            or Path(argument).suffix.casefold() in SENSITIVE_SUFFIXES
        ):
            raise ValueError("Host command arguments may not reference sensitive paths.")
        argument_path = Path(argument).expanduser()
        if argument_path.is_absolute() or "/" in argument or argument.startswith("."):
            resolved = (
                argument_path.resolve(strict=False)
                if argument_path.is_absolute()
                else (cwd / argument_path).resolve(strict=False)
            )
            assert_not_sensitive(resolved)

    uv_python_root = Path.home() / ".local" / "share" / "uv" / "python"
    trusted_read_roots = (
        (uv_python_root.resolve(),) if uv_python_root.is_dir() else ()
    )
    result = bounded_argv(
        root,
        argv,
        payload.get("timeout", 60),
        cwd=cwd,
        additional_roots=(cwd,),
        additional_read_roots=trusted_read_roots,
    )
    return {"action": "host_command", "argv": argv, "cwd": str(cwd), **result}


def compose_broker_environment(
    root: Path, compose_options: list[str]
) -> tuple[dict[str, str], tuple[str, ...], tuple[Path, ...]]:
    compose_files = [
        str(compose_options[index + 1])
        for index in range(0, len(compose_options), 2)
    ]
    if compose_files:
        raw_compose_file = compose_files[0]
        if Path(raw_compose_file).is_absolute():
            raise ValueError("Compose file must be a repository-relative path.")
        compose_file = (root / raw_compose_file).resolve(strict=False)
    else:
        compose_file = next(
            (
                candidate
                for candidate in (
                    root / "compose.yaml",
                    root / "compose.yml",
                    root / "docker-compose.yaml",
                    root / "docker-compose.yml",
                )
                if candidate.is_file()
            ),
            None,
        )
        if compose_file is None:
            return {}, (), ()
    if compose_file != root and root not in compose_file.parents:
        raise ValueError("Compose file is outside the selected repository.")

    environment_file = compose_file.parent / ".env"
    if not environment_file.exists():
        return {}, (), ()
    if environment_file.is_symlink() or not environment_file.is_file():
        raise ValueError("Compose environment file must be a regular file.")
    if environment_file.stat().st_size > 100_000:
        raise ValueError("Compose environment file exceeds the preparation limit.")
    ignored = run_broker_argv(
        ["git", "check-ignore", "--quiet", "--", str(environment_file.relative_to(root))],
        cwd=root,
        timeout=30,
    )
    if ignored["returncode"] != 0:
        raise ValueError("Compose environment file must be ignored by Git.")

    values = {
        key: value
        for key, value in load_env(environment_file).items()
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key)
    }
    return (
        values,
        tuple(value for value in values.values() if value),
        (environment_file.resolve(strict=True),),
    )


def command_action(action: str, root: Path, payload: dict) -> dict:
    argv = payload.get("argv")
    if not isinstance(argv, list) or not argv:
        raise ValueError("argv is required.")
    for argument in argv:
        lowered = str(argument).casefold()
        if (
            any(
                marker in lowered
                for marker in (".env", ".ssh", ".aws", "keychain", "credential")
            )
            or Path(str(argument)).suffix.casefold() in SENSITIVE_SUFFIXES
        ):
            raise ValueError("Command arguments may not reference sensitive paths.")
        candidate = Path(str(argument))
        if (
            candidate.is_absolute()
            or "/" in str(argument)
            or str(argument).startswith(".")
        ):
            resolved = (
                candidate.resolve(strict=False)
                if candidate.is_absolute()
                else (root / candidate).resolve(strict=False)
            )
            if resolved != root and root not in resolved.parents:
                raise ValueError(
                    "Command arguments may not reference paths outside the selected repository."
                )
    environment_overrides: dict[str, str] = {}
    redacted_values: tuple[str, ...] = ()
    sensitive_read_paths: tuple[Path, ...] = ()
    if action == "command":
        if "/" in str(argv[0]) or str(argv[0]) not in COMMAND_ALLOWLIST:
            raise ValueError("Command executable is not allowlisted.")
        if Path(str(argv[0])).name in {"python", "python3"} and any(
            arg in {"-c", "-"} for arg in argv[1:]
        ):
            raise ValueError("Inline Python is not allowed.")
    elif action == "git":
        if argv[0] == "git":
            argv = argv[1:]
        if not argv or argv[0] not in GIT_SUBCOMMANDS:
            raise ValueError("Git subcommand is not allowlisted.")
        argv = ["git", *argv]
    elif action in {"compose_read", "compose_change"}:
        if argv[:2] == ["docker", "compose"]:
            argv = argv[2:]
        compose_options = []
        while argv and argv[0] in {"-f", "--file"}:
            if len(argv) < 2 or not str(argv[1]).strip():
                raise ValueError("Compose file option requires a repository-relative path.")
            compose_options.extend(argv[:2])
            argv = argv[2:]
        allowed = (
            COMPOSE_READ_SUBCOMMANDS
            if action == "compose_read"
            else COMPOSE_CHANGE_SUBCOMMANDS
        )
        if not argv or argv[0] not in allowed:
            raise ValueError("Compose subcommand is not allowlisted for this action.")
        (
            environment_overrides,
            redacted_values,
            sensitive_read_paths,
        ) = compose_broker_environment(root, compose_options)
        argv = ["docker", "compose", *compose_options, *argv]
    result = bounded_argv(
        root,
        argv,
        payload.get("timeout", 60),
        allow_git_internal=action == "git",
        sensitive_read_paths=sensitive_read_paths,
        environment_overrides=environment_overrides,
        redacted_values=redacted_values,
    )
    return {"action": action, "argv": argv, **result}


def github_publish_action(root: Path, payload: dict) -> dict:
    repository_name = str(payload.get("repository_name") or "").strip()
    description = str(payload.get("description") or "").strip()
    if not _GITHUB_REPOSITORY_NAME.fullmatch(
        repository_name
    ) or repository_name.casefold().endswith(".git"):
        raise ValueError("GitHub repository name is invalid.")
    if len(description) > 350 or any(ord(character) < 32 for character in description):
        raise ValueError("GitHub repository description is invalid.")
    if GITHUB_OWNER != "chapter-N3xtron":
        raise ValueError("Custodian GitHub owner is not authorized.")

    def git(*arguments: str) -> dict:
        return run_broker_argv(["git", *arguments], cwd=root)

    tracked_status = git("status", "--porcelain", "--untracked-files=no")
    if tracked_status["returncode"] != 0:
        return {
            "ok": False,
            "action": "github_publish",
            "error": "Custodian could not verify repository status.",
        }
    if tracked_status["output"].strip():
        return {
            "ok": False,
            "action": "github_publish",
            "error": "Commit tracked repository changes before GitHub publication.",
        }
    branch = git("symbolic-ref", "--quiet", "--short", "HEAD")
    branch_name = branch["output"].strip()
    if branch["returncode"] != 0 or not branch_name:
        return {
            "ok": False,
            "action": "github_publish",
            "error": "GitHub publication requires an attached local branch.",
        }
    head = git("rev-parse", "--verify", "HEAD")
    if head["returncode"] != 0:
        return {
            "ok": False,
            "action": "github_publish",
            "error": "GitHub publication requires at least one local commit.",
        }

    account = run_broker_argv(["gh", "api", "user", "--jq", ".login"], cwd=root)
    if account["returncode"] != 0 or account["output"].strip() != GITHUB_OWNER:
        return {
            "ok": False,
            "action": "github_publish",
            "error": "Broker-held GitHub authority is unavailable for chapter-N3xtron.",
        }

    previous_origin = git("remote", "get-url", "origin")
    had_previous_origin = previous_origin["returncode"] == 0
    backup_remote = f"custodian-previous-origin-{secrets.token_hex(4)}"
    if had_previous_origin:
        renamed = git("remote", "rename", "origin", backup_remote)
        if renamed["returncode"] != 0:
            return {
                "ok": False,
                "action": "github_publish",
                "error": "Custodian could not preserve the existing origin.",
            }

    full_name = f"{GITHUB_OWNER}/{repository_name}"
    create_argv = ["gh", "repo", "create", full_name, "--private"]
    if description:
        create_argv.extend(["--description", description])
    create_argv.extend(["--source", ".", "--remote", "origin", "--push"])
    published = run_broker_argv(create_argv, cwd=root, timeout=300)
    if published["returncode"] != 0:
        current_origin = git("remote", "get-url", "origin")
        if current_origin["returncode"] == 0:
            git("remote", "remove", "origin")
        if had_previous_origin:
            git("remote", "rename", backup_remote, "origin")
        return {
            "ok": False,
            "action": "github_publish",
            "partial": True,
            "error": published["output"].strip() or "GitHub publication failed.",
        }

    if had_previous_origin:
        removed = git("remote", "remove", backup_remote)
        if removed["returncode"] != 0:
            return {
                "ok": False,
                "action": "github_publish",
                "partial": True,
                "error": "Repository was published, but the previous origin could not be removed.",
            }
    return {
        "ok": True,
        "action": "github_publish",
        "owner": GITHUB_OWNER,
        "repository": repository_name,
        "visibility": "private",
        "branch": branch_name,
        "repository_url": f"https://github.com/{full_name}",
        "origin_updated": True,
        "pushed": True,
    }


def preflight_host_file_action(payload: dict) -> dict:
    """Canonicalize and refuse a host path without opening or reading its content."""

    value = str(payload.get("path") or "").strip()
    reason = str(payload.get("reason") or "").strip()
    if not value or not Path(value).expanduser().is_absolute():
        raise ValueError("Path must be absolute.")
    if not reason:
        raise ValueError("A user-visible reason is required.")
    target = Path(value).expanduser().resolve(strict=False)
    assert_not_sensitive(target)
    notice_token = secrets.token_urlsafe(32)
    now = time.monotonic()
    with _NOTICE_LOCK:
        expired = [
            token
            for token, (_path, _reason, expiry) in _PENDING_HOST_FILE_NOTICES.items()
            if expiry <= now
        ]
        for token in expired:
            _PENDING_HOST_FILE_NOTICES.pop(token, None)
        _PENDING_HOST_FILE_NOTICES[notice_token] = (
            str(target),
            reason,
            now + _NOTICE_TTL_SECONDS,
        )
    return {
        "ok": True,
        "action": "preflight_host_file",
        "path": str(target),
        "reason": reason,
        "allowed": True,
        "notice_token": notice_token,
    }


def consume_host_file_notice(path: str, reason: str, notice_token: object) -> None:
    if not isinstance(notice_token, str) or not notice_token:
        raise ValueError("A prior visible host-file notice is required.")
    with _NOTICE_LOCK:
        notice = _PENDING_HOST_FILE_NOTICES.pop(notice_token, None)
    if notice is None:
        raise ValueError("The host-file notice is missing, expired, or already used.")
    noticed_path, noticed_reason, expires_at = notice
    if expires_at <= time.monotonic():
        raise ValueError("The host-file notice expired.")
    if noticed_path != path or noticed_reason != reason:
        raise ValueError("The host-file notice does not match this read.")


def read_host_file_action(payload: dict) -> dict:
    path_value = str(payload.get("path") or "").strip()
    reason = str(payload.get("reason") or "").strip()
    if not path_value:
        return {"ok": False, "action": "read_host_file", "error": "Missing path."}
    if not reason:
        return {
            "ok": False,
            "action": "read_host_file",
            "error": "Missing user-visible reason.",
        }
    try:
        consume_host_file_notice(path_value, reason, payload.get("notice_token"))
    except ValueError as error:
        return {"ok": False, "action": "read_host_file", "error": str(error)}
    candidate = Path(path_value).expanduser()
    if not candidate.is_absolute():
        return {
            "ok": False,
            "action": "read_host_file",
            "error": "Path must be absolute.",
        }
    try:
        target = candidate.resolve(strict=True)
    except OSError:
        return {"ok": False, "action": "read_host_file", "error": "File not found."}
    lowered_parts = {part.casefold() for part in target.parts}
    lowered_name = target.name.casefold()
    if (
        lowered_parts & FORBIDDEN_HOST_READ_PARTS
        or lowered_name.startswith(".env")
        or lowered_name in FORBIDDEN_HOST_READ_NAMES
        or target.suffix.casefold() in FORBIDDEN_HOST_READ_SUFFIXES
    ):
        return {
            "ok": False,
            "action": "read_host_file",
            "error": "Refusing credential, keychain, token, environment, private-key, or browser-credential material.",
        }
    if not target.is_file():
        return {
            "ok": False,
            "action": "read_host_file",
            "error": "Path is not a regular file.",
        }
    try:
        with target.open("rb") as file:
            sample = file.read(4096)
    except OSError as error:
        return {"ok": False, "action": "read_host_file", "error": str(error)}
    if b"\0" in sample:
        return {
            "ok": False,
            "action": "read_host_file",
            "error": "Binary files are not supported.",
        }
    try:
        max_chars = max(1, min(int(payload.get("max_chars") or 50000), 100000))
    except (TypeError, ValueError):
        max_chars = 50000
    try:
        text = target.read_text(errors="replace")
    except OSError as error:
        return {"ok": False, "action": "read_host_file", "error": str(error)}
    content = redact_text(text[:max_chars])
    return {
        "ok": True,
        "action": "read_host_file",
        "path": str(target),
        "reason": reason,
        "content": content,
        "truncated": len(text) > max_chars,
    }


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
        return {
            "ok": False,
            "action": "terminal_command",
            "error": "cwd is not a directory.",
            "cwd": cwd_value,
        }
    try:
        assert_terminal_command_allowed(command)
    except ValueError as error:
        return {
            "ok": False,
            "action": "terminal_command",
            "error": str(error),
            "command": command,
        }
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
            "stdout": (error.stdout or "")[-1500:]
            if isinstance(error.stdout, str)
            else "",
            "stderr": (error.stderr or "")[-800:]
            if isinstance(error.stderr, str)
            else "",
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
        return {
            "ok": False,
            "action": "replace_text",
            "error": "Missing old_text or new_text.",
        }
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
        return {
            "ok": False,
            "action": "apply_patch",
            "error": "Patch has no repo-relative paths.",
        }
    for rel_path in paths:
        if rel_path.startswith("/") or ".." in Path(rel_path).parts:
            return {
                "ok": False,
                "action": "apply_patch",
                "error": f"Unsafe patch path: {rel_path}",
            }
        assert_repo_write_allowed(safe_path(rel_path, root), root)
    check = run_command_input(["git", "apply", "--check", "-"], patch_text, cwd=root)
    if check["returncode"] != 0:
        return {
            "ok": False,
            "action": "apply_patch",
            "error": "Patch check failed.",
            "check": check,
        }
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
            name for name in dirnames if not is_ignored_path(current / name, root)
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
            inventory.append(
                f"- skipped {rel} ({size} bytes; total review character budget reached)"
            )
            continue

        text = path.read_text(errors="replace")
        redacted = redact_text(text)
        chunk = redacted[:max_chars_per_file]
        if len(redacted) > len(chunk):
            files_truncated += 1
            chunk += "\n\n[TRUNCATED: file excerpt limit reached]"

        remaining = max_total_chars - total_chars
        if len(chunk) > remaining:
            chunk = (
                chunk[:remaining]
                + "\n\n[TRUNCATED: total review character budget reached]"
            )

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
        + (
            run_command(["git", "status", "--short"], cwd=root)
            .get("stdout", "")
            .strip()
            or "Clean"
        )
        + "\n```\n\n"
        "## File Inventory\n\n"
        "```text\n"
        + "\n".join(inventory[:500])
        + ("\n[TRUNCATED: inventory limit reached]" if len(inventory) > 500 else "")
        + "\n```\n\n"
        "## Skipped Files\n\n"
        + ("\n".join(skipped[:250]) if skipped else "No files skipped.")
        + (
            "\n- [TRUNCATED: skipped-file list limit reached]"
            if len(skipped) > 250
            else ""
        )
        + "\n\n"
        "## Redacted File Excerpts\n\n"
        + (
            "\n\n".join(sections)
            if sections
            else "No readable text files found within bounds."
        )
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
    result = run_command(
        [RG_BIN, "--line-number", "--no-heading", "--color", "never", "-S", pattern],
        cwd=root,
    )
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
        result = run_host_command(
            ["docker", "exec", name, "python", "-c", script], timeout=10
        )
        checks.append(
            {
                "container": name,
                "url": url,
                "ok": result["returncode"] == 0
                and result["stdout"].strip().startswith(("2", "3")),
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
    container_hash = run_host_command(
        ["docker", "exec", "open-webui", "sha256sum", "/app/build/static/custom.css"]
    )
    container_tail = run_host_command(
        [
            "docker",
            "exec",
            "open-webui",
            "tail",
            "-n",
            "35",
            "/app/build/static/custom.css",
        ]
    )
    http_check = run_host_command(
        [
            "curl",
            "-sS",
            "-o",
            "/dev/null",
            "-w",
            "%{http_code}",
            "http://127.0.0.1:3000/static/custom.css",
        ]
    )

    local_sha = (
        (local_hash.get("stdout") or "").split()[0] if local_hash.get("stdout") else ""
    )
    mounted_sha = (
        (container_hash.get("stdout") or "").split()[0]
        if container_hash.get("stdout")
        else ""
    )
    return {
        "ok": bool(local_sha and mounted_sha and local_sha == mounted_sha),
        "action": "openwebui_theme_check",
        "local_sha": local_sha,
        "mounted_sha": mounted_sha,
        "mounted_matches_local": bool(
            local_sha and mounted_sha and local_sha == mounted_sha
        ),
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

    request_payload = json.dumps(
        {"limit": 50, "with_payload": True, "with_vector": False}
    ).encode("utf-8")
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
                    "text": (
                        item.get("text")
                        or item.get("assistant_text")
                        or item.get("user_text")
                        or ""
                    )[:1200],
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
    blocked = re.search(
        r"\b(CREATE|MERGE|SET|DELETE|DETACH|DROP|REMOVE|LOAD\s+CSV)\b", query, re.I
    )
    if blocked:
        return {
            "ok": False,
            "action": "graph_query",
            "error": "Only read-only Cypher queries are allowed through graph_query.",
        }
    result = run_host_command_input(
        [
            "docker",
            "exec",
            "-i",
            "memgraph-local",
            "mgconsole",
            "-output_format=tabular",
            "-no_history",
        ],
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
    qwen35 = container_url_check(
        "local-deep-research", ["http://host.docker.internal:7476/v1/models"]
    )[0]
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

    health = run_host_command(
        [
            "docker",
            "inspect",
            "--format",
            "{{.State.Health.Status}}",
            "local-deep-research",
        ]
    )
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
    if not path_is_allowed(target):
        raise ValueError("Repo path is outside allowed roots.")
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
        "allowed_tools": [
            "list",
            "read",
            "search",
            "git_status",
            "git_diff",
            "terminal_command",
            "write_file",
            "append_file",
            "replace_text",
            "delete_file",
            "apply_patch",
        ],
        "allowed_models": ["local", "codex-by-approval"],
        "approval_required": ["commit", "docker_restart", "ssh"],
    }
    REPOS_DIR.mkdir(parents=True, exist_ok=True)
    (REPOS_DIR / f"{repo_id}.json").write_text(json.dumps(repo, indent=2) + "\n")
    SELECTED_REPO_PATH.write_text(f"{repo_id}\n")
    return load_repo(repo_id)


def open_native_repo_picker() -> dict:
    script = (
        "POSIX path of (choose folder with prompt "
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
            "error": (
                result.stderr or result.stdout or "Folder picker cancelled."
            ).strip(),
        }
    selected_path = Path(result.stdout.strip())
    repo = register_repo_path(selected_path)
    return {"ok": True, "repo": repo}


def open_web_repo_picker() -> dict:
    try:
        browser_bundle = ENV.get(
            "CUSTODIAN_REPO_PICKER_BROWSER_BUNDLE", "com.brave.Browser"
        ).strip()
        command = (
            ["open", "-b", browser_bundle, repo_picker_url()]
            if browser_bundle
            else ["open", repo_picker_url()]
        )
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
        "selected_repo": (load_repo() if SELECTED_REPO_PATH.exists() else None),
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
    if any(
        term in text
        for term in [
            "terminal command",
            "shell command",
            "run command",
            "run test",
            "run tests",
            "run lint",
            "run build",
            "execute command",
        ]
    ):
        return {"action": "terminal_command"}
    if any(
        term in text
        for term in [
            "fix stack",
            "repair stack",
            "stack repair",
            "fix deep research",
            "fix ldr",
        ]
    ):
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
    if any(
        term in text
        for term in [
            "stack health",
            "container status",
            "docker status",
            "check stack",
            "stack logs",
        ]
    ):
        return {"action": "stack_health_check"}
    if any(
        term in text
        for term in [
            "theme check",
            "custom.css",
            "css bind",
            "css mount",
            "openwebui theme",
            "open webui theme",
        ]
    ):
        return {"action": "openwebui_theme_check"}
    if extract_first_url(request):
        return {"action": "fetch_url"}
    if any(
        term in text
        for term in [
            "full read",
            "full-read",
            "read all files",
            "read everything",
            "full repo read",
            "full repository read",
        ]
    ):
        return {"action": "full_repo_read_review"}
    if any(
        term in text
        for term in [
            "deep review",
            "standard review",
            "quick review",
            "security scan",
            "secret scan",
            "todo scan",
            "dependency audit",
        ]
    ):
        return {"action": "deep_repo_review"}
    llm_terms = [
        "llm",
        "local model",
        "model integration",
        "model selection",
        "ollama",
        "llama.cpp",
        "lm studio",
        "openai-compatible",
        "openai compatible",
        "qwen",
    ]
    if "repo" in text and any(term in text for term in llm_terms):
        return {"action": "llm_integration_scan"}
    if "read" in text and "repo" in text:
        return {"action": "repo_summary"}
    if any(word in text for word in ["read ", "open ", "show file", "inspect file"]):
        return {"action": "read"}
    if mode.strip().lower() == "select" or request_text.startswith(
        ("select repo", "change repo", "switch repo")
    ):
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


ACTION_SCHEMAS = {
    "preflight_host_file": {"required": {"path": str, "reason": str}},
    "read_host_file": {"required": {"path": str, "reason": str, "notice_token": str}},
    "fs_ls": {"required": {"repo": str, "path": str}},
    "fs_read": {"required": {"repo": str, "path": str}},
    "fs_revision": {"required": {"repo": str, "path": str}},
    "fs_glob": {"required": {"repo": str, "path": str, "pattern": str}},
    "fs_grep": {"required": {"repo": str, "path": str, "pattern": str}},
    "fs_write": {
        "required": {"repo": str, "path": str, "content": str, "expected_revision": str}
    },
    "fs_edit": {
        "required": {
            "repo": str,
            "path": str,
            "old_string": str,
            "new_string": str,
            "expected_revision": str,
        }
    },
    "fs_delete": {"required": {"repo": str, "path": str, "expected_revision": str}},
    "stage_ocr_document": {"required": {"repo": str, "path": str}},
    "write_ocr_output": {
        "required": {
            "repo": str,
            "path": str,
            "output_format": str,
        }
    },
    "execute": {"required": {"repo": str, "command": str}},
    "command": {"required": {"repo": str, "argv": list}},
    "host_command": {"required": {"repo": str, "argv": list, "cwd": str}},
    "git": {"required": {"repo": str, "argv": list}},
    "compose_prepare_environment": {
        "required": {"repo": str, "compose_file": str}
    },
    "compose_read": {"required": {"repo": str, "argv": list}},
    "compose_change": {"required": {"repo": str, "argv": list}},
    "github_publish": {
        "required": {"repo": str, "repository_name": str, "description": str}
    },
}


def validate_action_payload(action: str, payload: dict) -> None:
    schema = ACTION_SCHEMAS.get(action)
    # Picker endpoints retain their established schemas outside the agent API.
    if schema is None:
        raise ValueError("Unsupported agent action.")
    for field, expected_type in schema["required"].items():
        if field not in payload or not isinstance(payload[field], expected_type):
            raise ValueError(
                f"{field} is required and must be {expected_type.__name__}."
            )


def _execute_safe_action(action: str, payload: dict) -> dict:
    if action == "preflight_host_file":
        return preflight_host_file_action(payload)
    if action == "read_host_file":
        return read_host_file_action(payload)
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
    repo, root = bind_agent_workspace(payload)
    if action == "stage_ocr_document":
        return stage_ocr_document_action(root, payload)
    if action == "write_ocr_output":
        return write_ocr_output_action(root, payload)
    if action.startswith("fs_"):
        return fs_action(action, root, payload)
    if action == "execute":
        return execute_action(root, payload)
    if action == "compose_prepare_environment":
        return compose_prepare_environment_action(root, payload)
    if action == "host_command":
        return host_command_action(root, payload)
    if action in {"command", "git", "compose_read", "compose_change"}:
        return command_action(action, root, payload)
    if action == "github_publish":
        return github_publish_action(root, payload)
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
        for item in sorted(
            root.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())
        ):
            if item.name in {".git", "__pycache__"}:
                continue
            items.append(
                {
                    "name": item.name,
                    "path": str(item.relative_to(root)),
                    "type": "dir" if item.is_dir() else "file",
                }
            )
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
        for item in sorted(
            root.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())
        ):
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
            stdout = result.get("stdout", "").strip()
            if stdout:
                search_sections.append(
                    f"## Matches: {pattern}\n\n```text\n{stdout[:5000]}\n```"
                )

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
                key_files.append(
                    f"## {rel}\n\n```text\n{path.read_text(errors='replace')[:3000]}\n```"
                )

        content = (
            "# FrnT_DESK LLM Integration Scan\n\n"
            "## Top-level repo layout\n\n" + "\n".join(top_level) + "\n\n"
            "## Key config/docs excerpts\n\n" + "\n\n".join(key_files) + "\n\n"
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
        include_dirs = [
            "custodian",
            "deep-research",
            "ocr-service",
            "scripts",
            "searxng",
            "telegram-bridge",
        ]
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
            + (
                "\n".join(tree_lines(root, include_dirs, max_depth=3))
                or "No scoped directories found."
            )
            + "\n```\n\n"
            "## Git status\n\n"
            "```text\n"
            + (
                run_command(["git", "status", "--short"], cwd=root)
                .get("stdout", "")
                .strip()
                or "Clean"
            )
            + "\n```\n\n"
            "## TODO / FIXME / HACK matches\n\n"
            "```text\n"
            + (todo_matches or "No TODO/FIXME/HACK matches found.")
            + "\n```\n\n"
            "## Secret-pattern findings, redacted\n\n"
            + (
                "\n".join(secret_findings)
                if secret_findings
                else "No non-env secret-pattern findings found."
            )
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
            "logs": docker_logs_frontdesk(
                str(payload.get("container", "")), int(payload.get("tail", 120))
            ),
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
        for item in sorted(
            target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())
        ):
            if item.name in {".git", "__pycache__"}:
                continue
            items.append(
                {
                    "name": item.name,
                    "path": str(item.relative_to(root)),
                    "type": "dir" if item.is_dir() else "file",
                }
            )
        return {"ok": True, "action": action, "items": items}
    if action == "read":
        path_value = payload.get("path") or extract_path_from_request(
            str(payload.get("request", ""))
        )
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
        url = str(
            payload.get("url") or extract_first_url(str(payload.get("request", "")))
        ).strip()
        if not url:
            return {"ok": False, "error": "Missing URL.", "action": action}
        req = Request(url, headers={"User-Agent": "FrnT_DESK-Custodian/0.1"})
        tls_verified = True
        try:
            response = urlopen(req, timeout=20)
        except (ssl.SSLError, URLError) as error:
            reason = getattr(error, "reason", error)
            if isinstance(reason, ssl.SSLError) or "CERTIFICATE_VERIFY_FAILED" in str(
                error
            ):
                tls_verified = False
                response = urlopen(
                    req, timeout=20, context=ssl._create_unverified_context()
                )
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
        output = run_command(
            [RG_BIN, "--line-number", "--no-heading", "--color", "never", pattern],
            cwd=root,
        )
        return {"ok": True, "action": action, "query": pattern, **output}
    if action == "git_status":
        return {
            "ok": True,
            "action": action,
            **run_command(["git", "status", "--short"], cwd=root),
        }
    if action == "git_diff":
        return {
            "ok": True,
            "action": action,
            **run_command(["git", "diff", "--stat"], cwd=root),
        }
    return {
        "ok": False,
        "error": f"Unsupported safe action: {action}",
        "action": action,
    }


def execute_safe_action(action: str, payload: dict) -> dict:
    """Execute one explicitly named action and redact all returned text."""

    try:
        result = _execute_safe_action(action, payload)
    except (OSError, TypeError, ValueError) as error:
        result = {"ok": False, "action": action, "error": str(error)}
    return sanitize_text_outputs(result)


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(sanitize_text_outputs(payload), indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:3002")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def pick_folder(starting_path: str = "") -> dict:
    default_path = Path(starting_path).expanduser() if starting_path else Path.home()
    if not default_path.exists() or not default_path.is_dir():
        default_path = Path.home()
    script = """
    on run argv
    set defaultPath to POSIX file (item 1 of argv)
    tell application "Finder" to activate
    delay 0.2
    try
        set chosenFolder to choose folder with prompt "Select a repo or folder:" default location defaultPath
        return POSIX path of chosenFolder
    on error errorMessage number errorNumber
        if errorNumber is -128 then return "__CANCELLED__"
        error errorMessage number errorNumber
    end try
    end run
    """
    result = subprocess.run(
        ["osascript", "-e", script, str(default_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError("Folder picker failed to open")
    output = result.stdout.strip()
    if output == "__CANCELLED__" or not output:
        return {"ok": True, "path": None, "cancelled": True}
    return {"ok": True, "path": output, "cancelled": False}


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
    selected_label = (
        f"{selected['name']} — {selected['repo_path']}"
        if selected
        else "No repository selected"
    )

    def render_repo_row(item: dict[str, object]) -> str:
        select_button = (
            f'<button data-path="{escape(item["path"])}" data-name="{escape(item["name"])}" class="select-path">Select</button>'
            if item["is_git_repo"]
            else ""
        )
        return (
            "<tr>"
            f"<td><button data-path='{escape(item['path'])}' class='nav-folder'>Folder</button></td>"
            f"<td class='name'>{escape(item['name'])}</td>"
            f"<td>{'Git repo' if item['is_git_repo'] else 'Folder'}</td>"
            f"<td>{select_button}</td>"
            "</tr>"
        )

    rows = "\n".join(render_repo_row(item) for item in picker["dirs"])
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
    <code id="selected">{escape(selected_label)}</code>
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
      document.getElementById("selected").textContent = data.selected_repo
        ? data.selected_repo.name + " — " + data.selected_repo.repo_path
        : "No repository selected";
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
        window.parent.postMessage(
          {{ type: "custodian-repo-selected", path: data.repo.repo_path }},
          "http://127.0.0.1:3002",
        );
      await load(currentPath);
    }}
    async function selectRepo(repo) {{
      const data = await api("/repo/select", {{
        method:"POST",
        headers:{{"Content-Type":"application/json"}},
        body:JSON.stringify({{repo}})
      }});
      document.getElementById("status").textContent = "Selected " + data.repo.name;
        window.parent.postMessage(
          {{ type: "custodian-repo-selected", path: data.repo.repo_path }},
          "http://127.0.0.1:3002",
        );
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

            if parsed.path == "/api/fs/pick-folder":
                json_response(
                    self,
                    200,
                    pick_folder(query.get("starting_path", [""])[0]),
                )
                return

            if parsed.path == "/repo/browse":
                json_response(self, 200, browse_dirs(query.get("path", [""])[0]))
                return

            if parsed.path == "/status":
                json_response(
                    self,
                    200,
                    {
                        "ok": True,
                        "service": "custodian-worker",
                        "protocol": "native-custodian-v1",
                    },
                )
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
                target = (
                    (ALLOWED_ROOT / rel_path).resolve() if rel_path else ALLOWED_ROOT
                )
                repo = register_repo_path(target, name or None)
                json_response(self, 200, {"ok": True, "repo": repo})
                return

            if parsed.path == "/workspace/select":
                workspace_id = str(body.get("workspace_id", "")).strip()
                if not workspace_id:
                    json_response(
                        self, 400, {"ok": False, "error": "Missing workspace_id."}
                    )
                    return
                repo = find_repo(workspace_id)
                SELECTED_REPO_PATH.write_text(f"{repo['id']}\n")
                json_response(
                    self, 200, {"ok": True, "workspace": load_repo(repo["id"])}
                )
                return

            if parsed.path == "/task":
                if not request_is_authenticated(self):
                    json_response(
                        self,
                        401,
                        {"ok": False, "error": "Custodian authentication failed."},
                    )
                    return
                action = str(body.get("action") or "").strip()
                validate_action_payload(action, body)
                result = execute_safe_action(action, body)
                if result.get("ok"):
                    status = 200
                elif "Revision conflict" in str(result.get("error")):
                    status = 409
                else:
                    status = 400
                json_response(
                    self,
                    status,
                    {
                        "ok": bool(result.get("ok")),
                        "selected_action": action,
                        "result": result,
                    },
                )
                return
        except ValueError as error:
            json_response(self, 400, {"ok": False, "error": str(error)})
            return
        except Exception:
            json_response(
                self, 500, {"ok": False, "error": "Internal Custodian error."}
            )
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
    api_token()
    server = ThreadingHTTPServer((BIND_HOST, PORT), CustodianHandler)
    print(f"custodian-worker listening on http://{BIND_HOST}:{PORT}")
    print(f"allowed roots: {', '.join(str(root) for root in ALLOWED_ROOTS)}")
    server.serve_forever()


if __name__ == "__main__":
    main()
