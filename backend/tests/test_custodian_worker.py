from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

import custodian_worker


def _host_notice(path, reason):
    notice = custodian_worker.execute_safe_action(
        "preflight_host_file", {"path": str(path), "reason": reason}
    )
    assert notice["ok"] is True
    return {
        "path": notice["path"],
        "reason": notice["reason"],
        "notice_token": notice["notice_token"],
    }


def test_read_host_file_reads_text_and_redacts_secret_like_values(tmp_path):
    target = tmp_path / "notes.txt"
    target.write_text("status=ready\napi_key=abcdefghijklmnop")

    result = custodian_worker.execute_safe_action(
        "read_host_file",
        _host_notice(target, "Read the host notes requested by the human."),
    )

    assert result["ok"] is True
    assert result["path"] == str(target)
    assert result["reason"] == "Read the host notes requested by the human."
    assert "abcdefghijklmnop" not in result["content"]
    assert "api_key=REDACTED" in result["content"]


def test_read_host_file_rejects_secret_paths(tmp_path):
    target = tmp_path / ".env"
    target.write_text("TOKEN=secret-value")

    result = custodian_worker.execute_safe_action(
        "preflight_host_file",
        {"path": str(target), "reason": "Policy test."},
    )

    assert result["ok"] is False
    assert "Refusing credential" in result["error"]


def test_read_host_file_requires_visible_reason(tmp_path):
    target = tmp_path / "notes.txt"
    target.write_text("ordinary text")

    result = custodian_worker.execute_safe_action(
        "read_host_file",
        {"path": str(target)},
    )

    assert result == {
        "ok": False,
        "action": "read_host_file",
        "error": "Missing user-visible reason.",
    }


def _bind(monkeypatch, root):
    canonical = root.resolve()
    monkeypatch.setattr(custodian_worker, "ALLOWED_ROOT", canonical)
    return {"repo": str(canonical)}


def test_agent_filesystem_requires_exact_workspace_and_blocks_sensitive_walks(
    monkeypatch, tmp_path
):
    payload = _bind(monkeypatch, tmp_path)
    (tmp_path / "visible.txt").write_text("ready")
    (tmp_path / ".env.production").write_text("OPENAI_API_KEY=secret-secret")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("credential=secret-secret")

    missing = custodian_worker.execute_safe_action("fs_ls", {"path": "/"})
    listing = custodian_worker.execute_safe_action("fs_ls", {**payload, "path": "/"})
    globbed = custodian_worker.execute_safe_action(
        "fs_glob", {**payload, "path": "/", "pattern": "**/*"}
    )

    assert missing["ok"] is False
    assert [entry["path"] for entry in listing["entries"]] == ["/visible.txt"]
    assert all(".env" not in match["path"] for match in globbed["matches"])
    assert all(".git" not in match["path"] for match in globbed["matches"])


def test_checked_atomic_write_rejects_stale_revision_and_redacts_reads(
    monkeypatch, tmp_path
):
    payload = _bind(monkeypatch, tmp_path)
    target = tmp_path / "notes.txt"
    target.write_text("before")
    revision = custodian_worker.execute_safe_action(
        "fs_revision", {**payload, "path": "/notes.txt"}
    )["revision"]
    target.write_text("concurrent")

    stale = custodian_worker.execute_safe_action(
        "fs_write",
        {
            **payload,
            "path": "/notes.txt",
            "content": "api_key=abcdefghijklmnop",
            "expected_revision": revision,
        },
    )
    current = custodian_worker.execute_safe_action(
        "fs_revision", {**payload, "path": "/notes.txt"}
    )["revision"]
    written = custodian_worker.execute_safe_action(
        "fs_write",
        {
            **payload,
            "path": "/notes.txt",
            "content": "api_key=abcdefghijklmnop",
            "expected_revision": current,
        },
    )
    read = custodian_worker.execute_safe_action(
        "fs_read", {**payload, "path": "/notes.txt"}
    )

    assert stale["ok"] is False
    assert written["ok"] is True
    assert os.path.exists(target)
    assert "abcdefghijklmnop" not in read["file_data"]["content"]


def test_host_preflight_refuses_without_reading(monkeypatch, tmp_path):
    target = tmp_path / "ordinary.txt"
    target.write_text("ordinary")

    def fail_read(*_args, **_kwargs):
        raise AssertionError("preflight read file content")

    monkeypatch.setattr(type(target), "read_text", fail_read)
    result = custodian_worker.execute_safe_action(
        "preflight_host_file",
        {"path": str(target), "reason": "Read an ordinary host note."},
    )

    assert result["ok"] is True
    assert result["action"] == "preflight_host_file"
    assert result["path"] == str(target.resolve())
    assert result["reason"] == "Read an ordinary host note."
    assert result["allowed"] is True
    assert result["notice_token"]


def test_host_file_notice_is_one_use_and_bound_to_the_read(tmp_path):
    target = tmp_path / "ordinary.txt"
    target.write_text("ordinary")
    payload = _host_notice(target, "Read the requested note.")

    first = custodian_worker.execute_safe_action("read_host_file", payload)
    replay = custodian_worker.execute_safe_action("read_host_file", payload)

    assert first["ok"] is True
    assert replay["ok"] is False
    assert "already used" in replay["error"]


def test_commands_are_argv_only_allowlisted_and_environment_is_sanitized(
    monkeypatch, tmp_path
):
    payload = _bind(monkeypatch, tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "provider-secret")

    shell = custodian_worker.execute_safe_action(
        "command", {**payload, "argv": ["sh", "-c", "env"]}
    )
    inline_python = custodian_worker.execute_safe_action(
        "command", {**payload, "argv": ["python3", "-c", "print('x')"]}
    )

    assert shell["ok"] is False
    assert inline_python["ok"] is False
    assert "OPENAI_API_KEY" not in custodian_worker.sanitized_environment()


def test_git_tool_can_read_internal_metadata_but_rejects_remote_operations(
    monkeypatch, tmp_path
):
    payload = _bind(monkeypatch, tmp_path)
    initialized = custodian_worker.bounded_argv(
        tmp_path, ["git", "init"], allow_git_internal=True
    )

    status = custodian_worker.execute_safe_action(
        "git", {**payload, "argv": ["status", "--short"]}
    )
    remote = custodian_worker.execute_safe_action(
        "git", {**payload, "argv": ["push", "origin", "main"]}
    )

    assert initialized["ok"] is True
    assert status["ok"] is True
    assert remote["ok"] is False


def test_git_tool_supports_verified_linked_worktree_metadata(
    monkeypatch, tmp_path
):
    main = tmp_path / "main"
    linked = tmp_path / "linked"
    subprocess.run(["git", "init", str(main)], check=True, capture_output=True)
    (main / "tracked.txt").write_text("tracked\n")
    subprocess.run(
        ["git", "-C", str(main), "add", "tracked.txt"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "git",
            "-C",
            str(main),
            "-c",
            "user.name=Custodian Test",
            "-c",
            "user.email=custodian@example.invalid",
            "commit",
            "-m",
            "fixture",
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(main), "worktree", "add", "-b", "linked-test", str(linked)],
        check=True,
        capture_output=True,
    )
    payload = _bind(monkeypatch, linked)

    metadata_paths = custodian_worker.linked_worktree_git_paths(linked)
    status = custodian_worker.execute_safe_action(
        "git", {**payload, "argv": ["status", "--short"]}
    )

    assert len(metadata_paths) == 2
    assert all(linked not in path.parents for path in metadata_paths)
    assert status["ok"] is True


def test_command_allows_parent_metadata_but_not_sibling_content(monkeypatch):
    with tempfile.TemporaryDirectory(dir=Path.home()) as temporary:
        parent = Path(temporary)
        root = parent / "repo"
        root.mkdir()
        payload = _bind(monkeypatch, root)
        (parent / "outside.txt").write_text("OUTSIDE_SENTINEL")
        (root / "probe.py").write_text(
            "import os\n"
            "from pathlib import Path\n"
            "os.lstat(Path.cwd().parent)\n"
            "print('metadata-ok')\n"
            "print((Path.cwd().parent / 'outside.txt').read_text())\n"
        )

        result = custodian_worker.execute_safe_action(
            "command",
            {**payload, "argv": ["python3", "probe.py"], "timeout": 10},
        )

        assert result["ok"] is False
        assert "metadata-ok" in result["output"]
        assert "OUTSIDE_SENTINEL" not in result["output"]


def test_native_command_sandbox_refuses_sensitive_repo_file_reads(
    monkeypatch, tmp_path
):
    payload = _bind(monkeypatch, tmp_path)
    (tmp_path / ".env").write_text("HARMLESS_SENTINEL=not-a-secret")
    (tmp_path / "probe.py").write_text(
        'from pathlib import Path\nprint(Path(".env").read_text())\n'
    )

    result = custodian_worker.execute_safe_action(
        "command", {**payload, "argv": ["python3", "probe.py"], "timeout": 10}
    )

    assert result["ok"] is False
    assert "HARMLESS_SENTINEL" not in result["output"]
