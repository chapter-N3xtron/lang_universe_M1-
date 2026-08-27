from __future__ import annotations

import io
import urllib.error

from src import custodian_backend
from deepagents.backends.protocol import SandboxBackendProtocol

from src.custodian_backend import CustodianBackend, CustodianClient


class FakeClient:
    def __init__(self):
        self.calls = []
        self.revision = "revision-1"

    def action(self, action, **payload):
        self.calls.append((action, payload))
        if action == "fs_revision":
            return {"ok": True, "revision": self.revision}
        if action == "fs_read":
            return {
                "ok": True,
                "file_data": {"content": "one\ntwo\n", "encoding": "utf-8"},
                "start_line": 1,
                "end_line": 2,
                "total_lines": 2,
                "next_offset": 2,
            }
        if action == "fs_write":
            return {"ok": True, "path": payload["path"]}
        if action == "fs_edit":
            return {"ok": True, "path": payload["path"], "occurrences": 1}
        if action == "execute":
            return {
                "ok": True,
                "output": "tests passed",
                "exit_code": 0,
                "truncated": False,
            }
        return {"ok": True, "entries": []}


def test_client_authenticates_every_worker_action(monkeypatch):
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, _limit):
            return b'{"result":{"ok":true,"entries":[]}}'

    def urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(custodian_backend.urllib.request, "urlopen", urlopen)
    client = CustodianClient(
        "/Volumes/Storage/repo",
        base_url="http://127.0.0.1:8765",
        api_token="a" * 32,
    )

    result = client.action("fs_ls", path="/")

    assert result["ok"] is True
    assert captured["request"].get_header("Authorization") == f"Bearer {'a' * 32}"
    assert captured["timeout"] == 35.0


def test_client_returns_sanitized_worker_rejection(monkeypatch):
    response = io.BytesIO(
        b'{"result":{"ok":false,"error":"Command executable is not allowlisted."}}'
    )
    error = urllib.error.HTTPError(
        "http://127.0.0.1:8765/task", 400, "Bad Request", {}, response
    )

    def urlopen(_request, timeout):
        del timeout
        raise error

    monkeypatch.setattr(custodian_backend.urllib.request, "urlopen", urlopen)
    client = CustodianClient(
        "/Volumes/Storage/repo",
        base_url="http://127.0.0.1:8765",
        api_token="a" * 32,
    )

    result = client.action("command", argv=["unsupported"])

    assert result == {
        "ok": False,
        "error": "Command executable is not allowlisted.",
    }


def test_backend_implements_protocol_results_and_revision_preconditions():
    client = FakeClient()
    backend = CustodianBackend("/Volumes/Storage/repo", client=client)

    read = backend.read("/README.md")
    written = backend.write("/README.md", "updated")
    edited = backend.edit("/README.md", "old", "new")

    assert read.file_data["content"] == "one\ntwo\n"
    assert read.next_offset == 2
    assert written.path == "/README.md"
    assert edited.occurrences == 1
    mutation_calls = [call for call in client.calls if call[0] in {"fs_write", "fs_edit"}]
    assert all(call[1]["expected_revision"] == "revision-1" for call in mutation_calls)


def test_backend_exposes_documented_execute_through_sandbox_protocol():
    client = FakeClient()
    backend = CustodianBackend("/Volumes/Storage/repo", client=client)

    result = backend.execute("pytest -q", timeout=90)

    assert isinstance(backend, SandboxBackendProtocol)
    assert backend.id == "custodian:/Volumes/Storage/repo"
    assert result.output == "tests passed"
    assert result.exit_code == 0
    assert result.truncated is False
    assert client.calls == [("execute", {"command": "pytest -q", "timeout": 90})]


def test_backend_maps_only_selected_physical_workspace_paths_to_virtual_paths():
    client = FakeClient()
    workspace = "/Volumes/Storage/selected-repo"
    backend = CustodianBackend(workspace, client=client)

    backend.ls(workspace)
    backend.read(f"{workspace}/README.md")
    backend.write(f"{workspace}/notes.txt", "updated")

    assert client.calls[0] == ("fs_ls", {"path": "/"})
    assert client.calls[1][1]["path"] == "/README.md"
    assert client.calls[2] == ("fs_revision", {"path": "/notes.txt"})
    assert client.calls[3][1]["path"] == "/notes.txt"
    assert backend._virtual_path(f"{workspace}-other/file.txt") == (
        f"{workspace}-other/file.txt"
    )


def test_read_only_backend_refuses_all_mutations_without_worker_call():
    client = FakeClient()
    backend = CustodianBackend(
        "/Volumes/Storage/repo", read_only=True, client=client
    )

    assert backend.write("/x", "x").error == "Custodian backend is read-only"
    assert backend.edit("/x", "x", "y").error == "Custodian backend is read-only"
    assert backend.delete("/x").error == "Custodian backend is read-only"
    execution = backend.execute("pytest -q")
    assert execution.exit_code == 126
    assert execution.output == "Custodian backend is read-only."
    assert client.calls == []
