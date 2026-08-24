from __future__ import annotations

import base64
import os
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path

from docx import Document as WordDocument

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


def test_stage_ocr_document_copies_only_a_bounded_workspace_pdf(monkeypatch, tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    source = root / "RUBTTI.pdf"
    source.write_bytes(b"%PDF-1.7\nsource")
    upload_dir = tmp_path / "ocr-uploads"
    monkeypatch.setattr(custodian_worker, "OCR_UPLOAD_DIR", upload_dir)
    payload = _bind(monkeypatch, root)

    result = custodian_worker.execute_safe_action(
        "stage_ocr_document", {**payload, "path": "/RUBTTI.pdf"}
    )

    assert result["ok"] is True
    assert result["reference"].startswith("upload:")
    staged = upload_dir / result["reference"].removeprefix("upload:")
    assert staged.read_bytes() == source.read_bytes()
    assert source.read_bytes() == b"%PDF-1.7\nsource"

    text_file = root / "notes.txt"
    text_file.write_text("not a PDF")
    refused = custodian_worker.execute_safe_action(
        "stage_ocr_document", {**payload, "path": "/notes.txt"}
    )
    assert refused["ok"] is False
    assert "PDF files only" in refused["error"]

    monkeypatch.setattr(custodian_worker, "MAX_OCR_DOCUMENT_BYTES", 4)
    oversized = custodian_worker.execute_safe_action(
        "stage_ocr_document", {**payload, "path": "/RUBTTI.pdf"}
    )
    assert oversized["ok"] is False
    assert "25 MB limit" in oversized["error"]


def test_write_ocr_output_places_a_separate_file_beside_the_pdf(monkeypatch, tmp_path):
    root = tmp_path / "repo"
    source_dir = root / "documents"
    source_dir.mkdir(parents=True)
    source = source_dir / "RUBTTI.pdf"
    source.write_bytes(b"%PDF-1.7\nsource")
    payload = _bind(monkeypatch, root)

    result = custodian_worker.execute_safe_action(
        "write_ocr_output",
        {
            **payload,
            "path": "/documents/RUBTTI.pdf",
            "content": "recognized text",
            "output_format": "markdown",
        },
    )

    assert result == {
        "ok": True,
        "action": "write_ocr_output",
        "path": "/documents/RUBTTI.ocr.md",
        "size": len("recognized text"),
        "replaced": False,
    }
    assert (source_dir / "RUBTTI.ocr.md").read_text() == "recognized text"
    assert source.read_bytes() == b"%PDF-1.7\nsource"

    monkeypatch.setattr(custodian_worker, "MAX_OCR_OUTPUT_BYTES", 3)
    refused = custodian_worker.execute_safe_action(
        "write_ocr_output",
        {
            **payload,
            "path": "/documents/RUBTTI.pdf",
            "content": "too large",
            "output_format": "markdown",
        },
    )
    assert refused["ok"] is False
    assert "25 MB limit" in refused["error"]


def test_write_ocr_output_accepts_a_valid_docx(monkeypatch, tmp_path):
    root = tmp_path / "repo"
    source_dir = root / "documents"
    source_dir.mkdir(parents=True)
    source = source_dir / "RUBTTI.pdf"
    source.write_bytes(b"%PDF-1.7\nsource")
    payload = _bind(monkeypatch, root)
    document = WordDocument()
    document.add_paragraph("Recognized paragraph.")
    stream = BytesIO()
    document.save(stream)
    content = stream.getvalue()

    result = custodian_worker.execute_safe_action(
        "write_ocr_output",
        {
            **payload,
            "path": "/documents/RUBTTI.pdf",
            "content_base64": base64.b64encode(content).decode("ascii"),
            "output_format": "docx",
        },
    )

    assert result == {
        "ok": True,
        "action": "write_ocr_output",
        "path": "/documents/RUBTTI.ocr.docx",
        "size": len(content),
        "replaced": False,
    }
    assert (source_dir / "RUBTTI.ocr.docx").read_bytes() == content
    assert source.read_bytes() == b"%PDF-1.7\nsource"

    refused = custodian_worker.execute_safe_action(
        "write_ocr_output",
        {
            **payload,
            "path": "/documents/RUBTTI.pdf",
            "content_base64": "not-base64",
            "output_format": "docx",
        },
    )
    assert refused["ok"] is False
    assert "valid base64" in refused["error"]


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


def test_github_publish_uses_fixed_private_account_and_broker_authority(
    monkeypatch, tmp_path
):
    payload = _bind(monkeypatch, tmp_path)
    calls = []

    def run(argv, *, cwd, timeout=300):
        calls.append((argv, cwd, timeout))
        if argv[:3] == ["git", "status", "--porcelain"]:
            return {"returncode": 0, "output": ""}
        if argv[:4] == ["git", "symbolic-ref", "--quiet", "--short"]:
            return {"returncode": 0, "output": "feature/publish\n"}
        if argv[:3] == ["git", "rev-parse", "--verify"]:
            return {"returncode": 0, "output": "abc123\n"}
        if argv[:4] == ["gh", "api", "user", "--jq"]:
            return {"returncode": 0, "output": "chapter-N3xtron\n"}
        if argv[:4] == ["git", "remote", "get-url", "origin"]:
            return {"returncode": 0, "output": "git@example.invalid:old/repo.git\n"}
        return {"returncode": 0, "output": ""}

    monkeypatch.setattr(custodian_worker, "run_broker_argv", run)
    result = custodian_worker.execute_safe_action(
        "github_publish",
        {
            **payload,
            "repository_name": "new-private-repo",
            "description": "A private repository",
        },
    )

    publish_call = next(
        argv for argv, _cwd, _timeout in calls if argv[:3] == ["gh", "repo", "create"]
    )
    assert result["ok"] is True
    assert result["repository_url"] == (
        "https://github.com/chapter-N3xtron/new-private-repo"
    )
    assert "--private" in publish_call
    assert "--public" not in publish_call
    assert publish_call[3] == "chapter-N3xtron/new-private-repo"
    assert all(
        "token" not in " ".join(argv).casefold() for argv, _cwd, _timeout in calls
    )


def test_github_publish_rejects_dirty_tracked_changes_and_owner_injection(
    monkeypatch, tmp_path
):
    payload = _bind(monkeypatch, tmp_path)
    calls = []

    def dirty(argv, *, cwd, timeout=300):
        calls.append((argv, cwd, timeout))
        return {"returncode": 0, "output": " M tracked.py\n"}

    monkeypatch.setattr(custodian_worker, "run_broker_argv", dirty)
    dirty_result = custodian_worker.execute_safe_action(
        "github_publish",
        {**payload, "repository_name": "new-repo", "description": ""},
    )
    injected = custodian_worker.execute_safe_action(
        "github_publish",
        {**payload, "repository_name": "other-owner/repo", "description": ""},
    )

    assert dirty_result["ok"] is False
    assert "Commit tracked" in dirty_result["error"]
    assert injected["ok"] is False
    assert len(calls) == 1


def test_broker_environment_does_not_forward_environment_tokens(monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "not-forwarded")
    monkeypatch.setenv("GITHUB_TOKEN", "not-forwarded")

    environment = custodian_worker.broker_environment()

    assert environment["HOME"] == str(Path.home())
    assert "GH_TOKEN" not in environment
    assert "GITHUB_TOKEN" not in environment


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


def test_git_tool_supports_verified_linked_worktree_metadata(monkeypatch, tmp_path):
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
