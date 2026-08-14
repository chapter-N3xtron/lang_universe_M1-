from __future__ import annotations

import threading

from macos_host_executor.runner import SubprocessRunner


def test_runner_uses_bounded_output_and_minimal_environment(tmp_path) -> None:
    runner = SubprocessRunner(tmp_path / "stage")
    result = runner.run(
        ("/usr/bin/printf", "%5000s", "x"),
        cwd=None,
        timeout_seconds=2,
        output_limit_bytes=1024,
        cancel=threading.Event(),
    )
    assert result.exit_code == 0
    assert len(result.stdout.encode()) <= 512
    assert result.output_truncated


def test_runner_uses_isolated_home(tmp_path) -> None:
    runner = SubprocessRunner(tmp_path / "stage")
    result = runner.run(
        ("/usr/bin/env",),
        cwd=None,
        timeout_seconds=2,
        output_limit_bytes=4096,
        cancel=threading.Event(),
    )
    assert f"HOME={tmp_path / 'runtime-home'}" in result.stdout
    assert "SSH_AUTH_SOCK=" not in result.stdout
    assert "GH_TOKEN=" not in result.stdout
    assert "GITHUB_TOKEN=" not in result.stdout


def test_runner_timeout_targets_owned_process_group(tmp_path) -> None:
    runner = SubprocessRunner(tmp_path / "stage")
    result = runner.run(
        ("/bin/sleep", "2"),
        cwd=None,
        timeout_seconds=1,
        output_limit_bytes=1024,
        cancel=threading.Event(),
    )
    assert result.timed_out
    assert result.exit_code is not None


def test_runner_cancellation(tmp_path) -> None:
    runner = SubprocessRunner(tmp_path / "stage")
    cancel = threading.Event()
    cancel.set()
    result = runner.run(
        ("/bin/sleep", "2"),
        cwd=None,
        timeout_seconds=5,
        output_limit_bytes=1024,
        cancel=cancel,
    )
    assert result.cancelled
