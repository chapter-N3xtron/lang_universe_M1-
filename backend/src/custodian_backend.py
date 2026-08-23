"""Native Custodian client and documented Deep Agents filesystem backend."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from deepagents.backends.protocol import (
    BackendProtocol,
    DeleteResult,
    EditResult,
    GlobResult,
    GrepResult,
    LsResult,
    ReadResult,
    WriteResult,
)


class CustodianError(RuntimeError):
    """A bounded, non-sensitive Custodian request failure."""


def _custodian_api_token() -> str:
    value = os.getenv("CUSTODIAN_API_TOKEN", "").strip()
    if value:
        return value
    token_file = os.getenv(
        "CUSTODIAN_API_TOKEN_FILE", "/run/secrets/custodian_api_token"
    )
    try:
        token = Path(token_file).read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise CustodianError("Custodian authentication is unavailable") from exc
    if len(token) < 32:
        raise CustodianError("Custodian authentication is invalid")
    return token


@dataclass(frozen=True)
class CustodianClient:
    """Small authenticated JSON client for the native host Custodian."""

    workspace: str
    base_url: str = ""
    timeout: float = 35.0
    api_token: str = ""

    def __post_init__(self) -> None:
        if not self.workspace.startswith("/"):
            raise ValueError("Custodian workspace must be an absolute host path")
        if not self.base_url:
            object.__setattr__(
                self,
                "base_url",
                os.getenv(
                    "CUSTODIAN_WORKER_URL", "http://host.docker.internal:8765"
                ).rstrip("/"),
            )

    def action(self, action: str, **payload: Any) -> dict[str, Any]:
        token = self.api_token or _custodian_api_token()
        body = {"action": action, "repo": self.workspace, **payload}
        request = urllib.request.Request(
            f"{self.base_url}/task",
            data=json.dumps(body).encode(),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                envelope = json.loads(response.read(1_000_000).decode())
        except urllib.error.HTTPError as exc:
            try:
                envelope = json.loads(exc.read(1_000_000).decode())
            except (OSError, ValueError) as decode_exc:
                raise CustodianError("Custodian request failed") from decode_exc
        except (OSError, ValueError) as exc:
            raise CustodianError("Custodian request failed") from exc
        result = envelope.get("result", envelope)
        if not isinstance(result, dict):
            raise CustodianError("Custodian returned an invalid response")
        return result


class CustodianBackend(BackendProtocol):
    """BackendProtocol implementation rooted only at one host workspace."""

    def __init__(
        self,
        workspace: str,
        *,
        read_only: bool = False,
        client: CustodianClient | None = None,
    ) -> None:
        self.workspace = workspace
        self.read_only = read_only
        self.client = client or CustodianClient(workspace)

    @staticmethod
    def _error(result: dict[str, Any]) -> str | None:
        if result.get("ok") is True:
            return None
        return str(result.get("error") or "Custodian action failed")

    def _virtual_path(self, path: str) -> str:
        workspace = self.workspace.rstrip("/")
        if path in {workspace, f"{workspace}/"}:
            return "/"
        if path.startswith(f"{workspace}/"):
            return path[len(workspace) :]
        return path

    def ls(self, path: str) -> LsResult:
        try:
            result = self.client.action("fs_ls", path=self._virtual_path(path))
        except CustodianError as exc:
            return LsResult(error=str(exc))
        return LsResult(error=self._error(result), entries=result.get("entries"))

    def read(self, file_path: str, offset: int = 0, limit: int = 2000) -> ReadResult:
        try:
            result = self.client.action(
                "fs_read", path=self._virtual_path(file_path), offset=offset, limit=limit
            )
        except CustodianError as exc:
            return ReadResult(error=str(exc))
        error = self._error(result)
        if error:
            return ReadResult(error=error)
        kwargs: dict[str, Any] = {
            "file_data": result["file_data"],
            "start_line": result.get("start_line"),
            "end_line": result.get("end_line"),
            "total_lines": result.get("total_lines"),
            "next_offset": result.get("next_offset"),
        }
        # Empty files have no valid line window under the protocol.
        if kwargs["start_line"] is None:
            kwargs = {"file_data": result["file_data"]}
        return ReadResult(**kwargs)

    def grep(
        self,
        pattern: str,
        path: str | None = None,
        glob: str | None = None,
        *,
        max_count: int | None = None,
    ) -> GrepResult:
        try:
            result = self.client.action(
                "fs_grep",
                pattern=pattern,
                path=self._virtual_path(path) if path else "/",
                glob=glob,
                max_count=max_count,
            )
        except CustodianError as exc:
            return GrepResult(error=str(exc))
        return GrepResult(
            error=self._error(result),
            matches=result.get("matches"),
            truncated=bool(result.get("truncated")),
        )

    def glob(self, pattern: str, path: str | None = None) -> GlobResult:
        try:
            result = self.client.action(
                "fs_glob", pattern=pattern, path=self._virtual_path(path) if path else "/"
            )
        except CustodianError as exc:
            return GlobResult(error=str(exc))
        return GlobResult(
            error=self._error(result),
            matches=result.get("matches"),
            truncated=bool(result.get("truncated")),
        )

    def _revision(self, file_path: str) -> str:
        result = self.client.action("fs_revision", path=self._virtual_path(file_path))
        error = self._error(result)
        if error:
            raise CustodianError(error)
        return str(result["revision"])

    def write(self, file_path: str, content: str) -> WriteResult:
        if self.read_only:
            return WriteResult(error="Custodian backend is read-only")
        try:
            revision = self._revision(file_path)
            result = self.client.action(
                "fs_write",
                path=self._virtual_path(file_path),
                content=content,
                expected_revision=revision,
            )
        except CustodianError as exc:
            return WriteResult(error=str(exc))
        return WriteResult(error=self._error(result), path=result.get("path"))

    def edit(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> EditResult:
        if self.read_only:
            return EditResult(error="Custodian backend is read-only")
        try:
            revision = self._revision(file_path)
            result = self.client.action(
                "fs_edit",
                path=self._virtual_path(file_path),
                old_string=old_string,
                new_string=new_string,
                replace_all=replace_all,
                expected_revision=revision,
            )
        except CustodianError as exc:
            return EditResult(error=str(exc))
        return EditResult(
            error=self._error(result),
            path=result.get("path"),
            occurrences=result.get("occurrences"),
        )

    def delete(self, file_path: str) -> DeleteResult:
        if self.read_only:
            return DeleteResult(error="Custodian backend is read-only")
        try:
            revision = self._revision(file_path)
            result = self.client.action(
                "fs_delete", path=self._virtual_path(file_path), expected_revision=revision
            )
        except CustodianError as exc:
            return DeleteResult(error=str(exc))
        return DeleteResult(error=self._error(result), path=result.get("path"))
