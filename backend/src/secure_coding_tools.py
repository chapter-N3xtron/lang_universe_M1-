"""Workspace-confined mutation and command tools for the coding agent.

These tools are exposed only in explicit ``approval`` mode and every call is
wrapped by Deep Agents human-in-the-loop middleware. Validation is repeated in
the tool itself after approval so edited actions cannot bypass the policy.
"""

from __future__ import annotations

import asyncio
import os
import re
import signal
import tempfile
from pathlib import Path, PurePosixPath

from langchain_core.tools import BaseTool, StructuredTool, ToolException

MAX_WRITE_BYTES = 1_000_000
MAX_COMMAND_OUTPUT_BYTES = 100_000
MAX_COMMAND_TIMEOUT_SECONDS = 120

_SENSITIVE_PARTS = {".git", ".ssh", ".aws", ".gnupg"}
_SENSITIVE_NAMES = {"agents.md", "id_rsa", "id_ed25519"}
_SENSITIVE_SUFFIXES = {".key", ".pem", ".p12", ".pfx"}
_SHELL_TOKENS = {"|", "||", "&", "&&", ";", ">", ">>", "<", "<<"}
_ALLOWED_GIT_SUBCOMMANDS = {
    "diff",
    "log",
    "ls-files",
    "rev-parse",
    "show",
    "status",
}
_ALLOWED_SCRIPT_NAMES = {"build", "lint", "test", "typecheck"}
_DENIED_GIT_OPTIONS = {
    "--ext-diff",
    "--output",
    "--textconv",
}
_DENIED_RG_OPTIONS = {"--hostname-bin", "--pre", "--pre-glob"}
_SECRET_LINE = re.compile(
    r"(?im)^([A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD)[A-Z0-9_]*)\s*=\s*.+$"
)
_BEARER = re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+")


class CodingPolicyError(ToolException, ValueError):
    """A stable, non-sensitive policy failure."""


def _virtual_parts(file_path: str) -> tuple[str, ...]:
    if not isinstance(file_path, str) or not file_path.startswith("/"):
        raise CodingPolicyError("path_must_be_virtual_absolute")
    parts = PurePosixPath(file_path.replace("\\", "/")).parts[1:]
    if not parts or any(part in {"", ".", "..", "~"} for part in parts):
        raise CodingPolicyError("invalid_path")
    lowered = {part.lower() for part in parts}
    name = parts[-1].lower()
    if (
        lowered & _SENSITIVE_PARTS
        or name in _SENSITIVE_NAMES
        or name == ".env"
        or name.startswith(".env.")
        or Path(name).suffix in _SENSITIVE_SUFFIXES
    ):
        raise CodingPolicyError("sensitive_path")
    return parts


def resolve_mutation_path(workspace: Path, file_path: str) -> Path:
    """Resolve a virtual file path and reject traversal and symlink escapes."""
    workspace = workspace.resolve(strict=True)
    parts = _virtual_parts(file_path)
    candidate = workspace.joinpath(*parts)
    try:
        parent = candidate.parent.resolve(strict=True)
    except OSError as exc:
        raise CodingPolicyError("parent_not_found") from exc
    if not parent.is_relative_to(workspace):
        raise CodingPolicyError("workspace_escape")
    if candidate.exists() or candidate.is_symlink():
        try:
            resolved = candidate.resolve(strict=True)
        except OSError as exc:
            raise CodingPolicyError("invalid_target") from exc
        if not resolved.is_relative_to(workspace):
            raise CodingPolicyError("workspace_escape")
        candidate = resolved
    return candidate


def _atomic_write(path: Path, content: str) -> None:
    encoded = content.encode("utf-8")
    if len(encoded) > MAX_WRITE_BYTES:
        raise CodingPolicyError("content_too_large")
    descriptor, temporary_name = tempfile.mkstemp(prefix=".coding-agent-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _write_file(workspace: Path, file_path: str, content: str) -> str:
    target = resolve_mutation_path(workspace, file_path)
    _atomic_write(target, content)
    return "write_completed"


def _edit_file(
    workspace: Path,
    file_path: str,
    old_string: str,
    new_string: str,
    replace_all: bool = False,
) -> str:
    target = resolve_mutation_path(workspace, file_path)
    if not target.is_file():
        raise CodingPolicyError("file_not_found")
    try:
        original = target.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise CodingPolicyError("file_not_text") from exc
    if len(original.encode("utf-8")) > MAX_WRITE_BYTES:
        raise CodingPolicyError("content_too_large")
    occurrences = original.count(old_string)
    if not old_string or occurrences == 0:
        raise CodingPolicyError("old_string_not_found")
    if occurrences > 1 and not replace_all:
        raise CodingPolicyError("old_string_not_unique")
    updated = original.replace(old_string, new_string, -1 if replace_all else 1)
    _atomic_write(target, updated)
    return "edit_completed"


def validate_command_argv(argv: list[str]) -> list[str]:
    """Validate a command as argv; shell strings are never accepted."""
    if not isinstance(argv, list) or not argv or len(argv) > 64:
        raise CodingPolicyError("invalid_argv")
    if not all(isinstance(arg, str) and arg and len(arg) <= 4096 for arg in argv):
        raise CodingPolicyError("invalid_argv")
    for arg in argv:
        if "\x00" in arg or "\n" in arg or "\r" in arg:
            raise CodingPolicyError("invalid_character")
        if arg in _SHELL_TOKENS or "$(`" in arg or "$(" in arg or "`" in arg:
            raise CodingPolicyError("shell_syntax_denied")
        value = arg.split("=", 1)[-1] if arg.startswith("-") and "=" in arg else arg
        if value.startswith(("/", "~")) or ".." in PurePosixPath(value).parts:
            raise CodingPolicyError("workspace_escape")

    executable = argv[0]
    if executable == "git":
        if len(argv) < 2 or argv[1] not in _ALLOWED_GIT_SUBCOMMANDS:
            raise CodingPolicyError("command_denied")
        if any(arg.split("=", 1)[0] in _DENIED_GIT_OPTIONS for arg in argv[2:]):
            raise CodingPolicyError("command_denied")
    elif executable in {"pytest", "rg"}:
        if executable == "rg" and any(
            arg.split("=", 1)[0] in _DENIED_RG_OPTIONS for arg in argv[1:]
        ):
            raise CodingPolicyError("command_denied")
    elif executable == "ruff":
        if len(argv) < 2 or argv[1] not in {"check", "format"}:
            raise CodingPolicyError("command_denied")
        if argv[1] == "format" and "--check" not in argv:
            raise CodingPolicyError("command_denied")
    elif executable == "python":
        if argv[1:3] not in (["-m", "pytest"], ["-m", "compileall"]):
            raise CodingPolicyError("command_denied")
    elif executable in {"npm", "pnpm"}:
        arguments = argv[1:]
        if arguments[:1] == ["run"]:
            arguments = arguments[1:]
        if not arguments or arguments[0] not in _ALLOWED_SCRIPT_NAMES:
            raise CodingPolicyError("command_denied")
    else:
        raise CodingPolicyError("command_denied")
    return argv


def _validate_existing_command_paths(workspace: Path, argv: list[str]) -> None:
    """Reject existing path arguments that resolve through a workspace escape."""
    workspace = workspace.resolve(strict=True)
    for argument in argv[1:]:
        if argument.startswith("-"):
            continue
        candidate = workspace / argument
        if not (candidate.exists() or candidate.is_symlink()):
            continue
        try:
            resolved = candidate.resolve(strict=True)
        except OSError as exc:
            raise CodingPolicyError("invalid_command_path") from exc
        if not resolved.is_relative_to(workspace):
            raise CodingPolicyError("workspace_escape")


def _command_environment(workspace: Path) -> dict[str, str]:
    path_entries = [
        workspace / ".venv" / "bin",
        workspace / "node_modules" / ".bin",
        Path("/opt/homebrew/bin"),
        Path("/usr/local/bin"),
        Path("/usr/bin"),
        Path("/bin"),
    ]
    return {
        "PATH": os.pathsep.join(str(path) for path in path_entries),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "NO_COLOR": "1",
        "PYTHONNOUSERSITE": "1",
    }


def redact_command_output(output: str) -> str:
    output = _SECRET_LINE.sub(r"\1=[REDACTED]", output)
    return _BEARER.sub("Bearer [REDACTED]", output)


async def _run_command(
    workspace: Path, argv: list[str], timeout: int = 60
) -> str:
    argv = validate_command_argv(argv)
    _validate_existing_command_paths(workspace, argv)
    if timeout <= 0 or timeout > MAX_COMMAND_TIMEOUT_SECONDS:
        raise CodingPolicyError("invalid_timeout")
    try:
        process = await asyncio.create_subprocess_exec(
            *argv,
            cwd=workspace,
            env=_command_environment(workspace),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=True,
        )
    except OSError as exc:
        raise CodingPolicyError("command_unavailable") from exc
    try:
        output, _ = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except TimeoutError as exc:
        os.killpg(process.pid, signal.SIGKILL)
        await process.wait()
        raise CodingPolicyError("command_timeout") from exc
    truncated = len(output) > MAX_COMMAND_OUTPUT_BYTES
    rendered = output[:MAX_COMMAND_OUTPUT_BYTES].decode("utf-8", errors="replace")
    rendered = redact_command_output(rendered)
    suffix = "\n[output truncated]" if truncated else ""
    return f"exit_code={process.returncode}\n{rendered}{suffix}"


def create_approval_tools(workspace: Path) -> list[BaseTool]:
    """Build tools whose closures are confined to one validated workspace."""

    def approved_write_file(file_path: str, content: str) -> str:
        """Write a UTF-8 file after explicit human approval."""
        return _write_file(workspace, file_path, content)

    def approved_edit_file(
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> str:
        """Replace exact text in a UTF-8 file after explicit human approval."""
        return _edit_file(
            workspace, file_path, old_string, new_string, replace_all=replace_all
        )

    async def run_workspace_command(argv: list[str], timeout: int = 60) -> str:
        """Run an allowlisted argv command after explicit human approval."""
        return await _run_command(workspace, argv, timeout)

    return [
        StructuredTool.from_function(
            approved_write_file,
            name="approved_write_file",
            handle_tool_error=True,
        ),
        StructuredTool.from_function(
            approved_edit_file,
            name="approved_edit_file",
            handle_tool_error=True,
        ),
        StructuredTool.from_function(
            coroutine=run_workspace_command,
            name="run_workspace_command",
            handle_tool_error=True,
        ),
    ]


APPROVAL_INTERRUPT_ON = {
    "approved_write_file": {
        "allowed_decisions": ["approve", "edit", "reject"],
        "description": "Review a workspace-confined file write.",
    },
    "approved_edit_file": {
        "allowed_decisions": ["approve", "edit", "reject"],
        "description": "Review a workspace-confined file edit.",
    },
    "run_workspace_command": {
        "allowed_decisions": ["approve", "edit", "reject"],
        "description": "Review an argv-only allowlisted workspace command.",
    },
}
