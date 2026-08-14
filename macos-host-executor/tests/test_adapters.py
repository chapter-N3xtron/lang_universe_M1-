from __future__ import annotations

import hashlib
import io
import socket
import stat
import tarfile
import threading
import urllib.error
import zipfile
from email.message import Message
from pathlib import Path

import pytest

import macos_host_executor.adapters as adapters
from macos_host_executor.adapters import (
    ApplicationAdapter,
    DownloadAdapter,
    HomebrewAdapter,
    NativeApplicationAdapter,
    _bounded_content_length,
    _resolve_public_https_host,
    _safe_zip_extract,
    _verify_archive,
)
from macos_host_executor.models import (
    ApplicationInstallAction,
    DownloadAction,
    HomebrewAction,
    NativeApplicationAction,
)
from macos_host_executor.policy import ExecutionPlan
from macos_host_executor.runner import RunResult


def run_result(
    exit_code: int = 0,
    *,
    stdout: str = "",
    stderr: str = "",
    timed_out: bool = False,
    cancelled: bool = False,
) -> RunResult:
    return RunResult(
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        output_truncated=False,
        timed_out=timed_out,
        cancelled=cancelled,
        pid=123,
    )


class FakeResponse:
    def __init__(
        self,
        url: str,
        body: bytes,
        *,
        status: int = 200,
        content_length: str | None = None,
    ) -> None:
        self.url = url
        self.body = io.BytesIO(body)
        self.status = status
        self.headers = {}
        if content_length is not None:
            self.headers["Content-Length"] = content_length
        self.closed = False

    def getcode(self) -> int:
        return self.status

    def geturl(self) -> str:
        return self.url

    def read(self, size: int = -1) -> bytes:
        return self.body.read(size)

    def close(self) -> None:
        self.closed = True

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class FakeOpener:
    def __init__(self, values: list[object]) -> None:
        self.values = values
        self.calls: list[str] = []

    def open(self, request, timeout: int):  # type: ignore[no-untyped-def]
        self.calls.append(request.full_url)
        value = self.values.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def redirect(url: str, location: str) -> urllib.error.HTTPError:
    headers = Message()
    headers["Location"] = location
    return urllib.error.HTTPError(url, 302, "redirect", headers, io.BytesIO())


def download_action(
    destination: Path, body: bytes, **updates: object
) -> DownloadAction:
    values: dict[str, object] = {
        "category": "https_download",
        "url": "https://download.blender.org/file.zip",
        "destination": str(destination),
        "sha256": hashlib.sha256(body).hexdigest(),
        "max_bytes": 1024,
        "redirect_limit": 1,
        "archive": "none",
    }
    values.update(updates)
    return DownloadAction.model_validate(values)


def download_plan(destination: Path) -> ExecutionPlan:
    return ExecutionPlan(
        category="https_download",
        executable="builtin:https",
        argv=("GET", "https://download.blender.org/file.zip"),
        approved_paths=(str(destination),),
        rollback_strategy="remove_created_destination",
    )


def public_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ],
    )


def test_downloader_disables_proxies_and_rejects_non_public_dns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9999")
    captured_handlers: list[object] = []
    real_build_opener = adapters.urllib.request.build_opener

    def capture_build_opener(*handlers: object):
        captured_handlers.extend(handlers)
        return real_build_opener(*handlers)

    monkeypatch.setattr(adapters.urllib.request, "build_opener", capture_build_opener)
    DownloadAdapter(tmp_path, ("download.blender.org",))
    proxy_handlers = [
        handler
        for handler in captured_handlers
        if isinstance(handler, adapters.urllib.request.ProxyHandler)
    ]
    assert len(proxy_handlers) == 1 and proxy_handlers[0].proxies == {}

    for address in (
        "127.0.0.1",
        "10.0.0.1",
        "169.254.1.1",
        "224.0.0.1",
        "240.0.0.1",
        "0.0.0.0",
        "::1",
        "fe80::1",
        "ff02::1",
        "::",
    ):
        monkeypatch.setattr(
            socket,
            "getaddrinfo",
            lambda *args, address=address, **kwargs: [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))
            ],
        )
        with pytest.raises(ValueError, match="non-public"):
            _resolve_public_https_host("https://download.blender.org/file")


def test_downloader_revalidates_dns_on_redirect_and_rejects_invalid_hops(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "result"
    action = download_action(destination, b"ok")
    opener = FakeOpener(
        [
            redirect(action.url, "/next"),
            FakeResponse("https://download.blender.org/next", b"ok"),
        ]
    )
    adapter = DownloadAdapter(tmp_path / "stage", ("download.blender.org",))
    adapter.opener = opener  # type: ignore[assignment]
    addresses = iter(("93.184.216.34", "127.0.0.1"))
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (next(addresses), 443))
        ],
    )
    result = adapter.execute(
        action,
        download_plan(destination),
        timeout=2,
        output_limit=1024,
        cancel=threading.Event(),
    )
    assert not result.success
    assert "non-public" in result.message
    assert opener.calls == [action.url]
    assert not destination.exists()

    bad = FakeOpener([redirect(action.url, " /next")])
    adapter.opener = bad  # type: ignore[assignment]
    public_dns(monkeypatch)
    result = adapter.execute(
        action,
        download_plan(destination),
        timeout=2,
        output_limit=1024,
        cancel=threading.Event(),
    )
    assert not result.success and "Location is invalid" in result.message


def test_downloader_bounds_lengths_checksum_and_partial_copy_rollback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(ValueError, match="unbounded"):
        _bounded_content_length("9" * 20)
    with pytest.raises(ValueError, match="exceeds"):
        _bounded_content_length("10000", maximum=100)

    public_dns(monkeypatch)
    destination = tmp_path / "result"
    body = b"approved"
    adapter = DownloadAdapter(tmp_path / "stage", ("download.blender.org",))
    adapter.opener = FakeOpener(  # type: ignore[assignment]
        [FakeResponse("https://download.blender.org/file.zip", body)]
    )
    action = download_action(destination, body, sha256="0" * 64)
    result = adapter.execute(
        action,
        download_plan(destination),
        timeout=2,
        output_limit=1024,
        cancel=threading.Event(),
    )
    assert not result.success and "checksum" in result.message
    assert not destination.exists()

    adapter.opener = FakeOpener(  # type: ignore[assignment]
        [FakeResponse("https://download.blender.org/file.zip", body)]
    )
    action = download_action(destination, body)

    def fail_copy(source, output):  # type: ignore[no-untyped-def]
        output.write(source.read(2))
        raise OSError("fake destination write failure")

    monkeypatch.setattr(adapters.shutil, "copyfileobj", fail_copy)
    result = adapter.execute(
        action,
        download_plan(destination),
        timeout=2,
        output_limit=1024,
        cancel=threading.Event(),
    )
    assert not result.success
    assert result.rollback.attempted and result.rollback.succeeded
    assert not result.partial and not destination.exists()


def test_download_rollback_never_deletes_replaced_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    public_dns(monkeypatch)
    destination = tmp_path / "result"
    body = b"approved"
    adapter = DownloadAdapter(tmp_path / "stage", ("download.blender.org",))
    adapter.opener = FakeOpener(  # type: ignore[assignment]
        [FakeResponse("https://download.blender.org/file.zip", body)]
    )

    def replace_copy(source, output):  # type: ignore[no-untyped-def]
        output.write(source.read())
        destination.unlink()
        destination.write_bytes(b"not-owned")

    monkeypatch.setattr(adapters.shutil, "copyfileobj", replace_copy)
    result = adapter.execute(
        download_action(destination, body),
        download_plan(destination),
        timeout=2,
        output_limit=1024,
        cancel=threading.Event(),
    )
    assert not result.success and result.partial
    assert result.rollback.succeeded is False
    assert destination.read_bytes() == b"not-owned"


def test_archive_limits_special_types_and_failed_extraction_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tar_path = tmp_path / "special.tar.gz"
    with tarfile.open(tar_path, "w:gz") as archive:
        member = tarfile.TarInfo("device")
        member.type = tarfile.FIFOTYPE
        archive.addfile(member)
    with pytest.raises(ValueError, match="special types"):
        _verify_archive(tar_path, "tar_gz")

    zip_path = tmp_path / "special.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        member = zipfile.ZipInfo("link")
        member.create_system = 3
        member.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(member, "target")
    with pytest.raises(ValueError, match="special types"):
        _verify_archive(zip_path, "zip")

    many = tmp_path / "many.zip"
    with zipfile.ZipFile(many, "w") as archive:
        archive.writestr("one", "1")
        archive.writestr("two", "2")
    monkeypatch.setattr(adapters, "MAX_ARCHIVE_MEMBERS", 1)
    with pytest.raises(ValueError, match="member count"):
        _verify_archive(many, "zip")
    monkeypatch.setattr(adapters, "MAX_ARCHIVE_MEMBERS", 10_000)

    duplicate = tmp_path / "duplicate.zip"
    with zipfile.ZipFile(duplicate, "w") as archive:
        archive.writestr("same", "one")
        archive.writestr("same", "two")
    extraction = tmp_path / "private-extraction"
    extraction.mkdir(mode=0o700)
    with zipfile.ZipFile(duplicate) as archive, pytest.raises(FileExistsError):
        _safe_zip_extract(archive, extraction)
    assert not extraction.exists()


def test_homebrew_failure_is_not_verified() -> None:
    class FailedRunner:
        calls = 0

        def run(self, *args, **kwargs) -> RunResult:  # type: ignore[no-untyped-def]
            self.calls += 1
            return run_result(1, stderr="fake brew failure")

    runner = FailedRunner()
    result = HomebrewAdapter(runner).execute(
        HomebrewAction(
            category="homebrew",
            operation="install",
            package_kind="cask",
            package="blender",
        ),
        ExecutionPlan(
            category="homebrew",
            executable="/opt/homebrew/bin/brew",
            argv=("/opt/homebrew/bin/brew", "install", "--cask", "blender"),
        ),
        timeout=2,
        output_limit=1024,
        cancel=threading.Event(),
    )
    assert not result.success and not result.verified and runner.calls == 1


class NativeRunner:
    def __init__(
        self, output: Path, kind: str, result: RunResult | None = None
    ) -> None:
        self.output = output
        self.kind = kind
        self.result = result or run_result()
        self.calls = 0

    def run(self, *args, **kwargs) -> RunResult:  # type: ignore[no-untyped-def]
        self.calls += 1
        if self.kind == "file":
            self.output.write_bytes(b"render")
        elif self.kind == "empty":
            self.output.touch()
        elif self.kind == "directory":
            self.output.mkdir()
        return self.result


def native_action(tmp_path: Path, output: Path) -> NativeApplicationAction:
    input_path = tmp_path / "scene.blend"
    input_path.write_bytes(b"scene")
    return NativeApplicationAction(
        category="native_application",
        application_id="org.blender.Blender",
        operation="blender_background_render",
        working_directory=str(tmp_path),
        input_path=str(input_path),
        output_path=str(output),
    )


def native_plan(tmp_path: Path, output: Path) -> ExecutionPlan:
    return ExecutionPlan(
        category="native_application",
        executable="/Applications/Blender.app/Contents/MacOS/Blender",
        argv=("Blender", "--background"),
        working_directory=str(tmp_path),
        approved_paths=(str(tmp_path), str(output)),
    )


@pytest.mark.parametrize("kind", ["empty", "directory"])
def test_blender_requires_absent_then_nonempty_bounded_regular_output(
    tmp_path: Path, kind: str
) -> None:
    output = tmp_path / "render.png"
    action = native_action(tmp_path, output)
    result = NativeApplicationAdapter(NativeRunner(output, kind)).execute(
        action,
        native_plan(tmp_path, output),
        timeout=2,
        output_limit=1024,
        cancel=threading.Event(),
    )
    assert not result.verified and result.partial

    if output.is_dir():
        output.rmdir()
    else:
        output.unlink()
    output.write_bytes(b"preexisting")
    runner = NativeRunner(output, "file")
    result = NativeApplicationAdapter(runner).execute(
        action,
        native_plan(tmp_path, output),
        timeout=2,
        output_limit=1024,
        cancel=threading.Event(),
    )
    assert not result.success and runner.calls == 0
    assert output.read_bytes() == b"preexisting"


def test_blender_rejects_oversized_regular_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "render.png"
    action = native_action(tmp_path, output)
    monkeypatch.setattr(adapters, "MAX_NATIVE_OUTPUT_BYTES", 2)
    result = NativeApplicationAdapter(NativeRunner(output, "file")).execute(
        action,
        native_plan(tmp_path, output),
        timeout=2,
        output_limit=1024,
        cancel=threading.Event(),
    )
    assert not result.verified and result.partial


@pytest.mark.parametrize(
    "failure", [run_result(-15, timed_out=True), run_result(-15, cancelled=True)]
)
def test_blender_timeout_or_cancellation_with_output_is_partial(
    tmp_path: Path, failure: RunResult
) -> None:
    output = tmp_path / "render.png"
    action = native_action(tmp_path, output)
    runner = NativeRunner(output, "file", failure)
    result = NativeApplicationAdapter(runner).execute(
        action,
        native_plan(tmp_path, output),
        timeout=1,
        output_limit=1024,
        cancel=threading.Event(),
    )
    assert not result.success and not result.verified and result.partial


class DmgRunner:
    def __init__(
        self, *, attach_exit: int = 0, detach_exit: int = 0, verify_exit: int = 0
    ) -> None:
        self.attach_exit = attach_exit
        self.detach_exit = detach_exit
        self.verify_exit = verify_exit

    def run(self, argv, **kwargs) -> RunResult:  # type: ignore[no-untyped-def]
        if argv[0:2] == ("/usr/bin/hdiutil", "attach"):
            mount = Path(argv[argv.index("-mountpoint") + 1])
            (mount / "Blender.app" / "Contents").mkdir(parents=True)
            return run_result(self.attach_exit)
        if argv[0:2] == ("/usr/bin/hdiutil", "detach"):
            return run_result(self.detach_exit)
        if argv[0:2] == ("/usr/bin/codesign", "--verify"):
            return run_result(self.verify_exit)
        if argv[0:2] == ("/usr/bin/codesign", "-dv"):
            return run_result(stderr="TeamIdentifier=JCKZK6G8RJ\n")
        if argv[0] == "/usr/sbin/spctl":
            return run_result()
        raise AssertionError(argv)


def application_action(artifact: Path, destination: Path) -> ApplicationInstallAction:
    return ApplicationInstallAction(
        category="application_install",
        artifact_path=str(artifact),
        artifact_sha256="a" * 64,
        artifact_kind="dmg",
        application_id="org.blender.Blender",
        destination=str(destination),
        mode="stage",
        require_team_id="JCKZK6G8RJ",
    )


def application_plan(artifact: Path, destination: Path) -> ExecutionPlan:
    return ExecutionPlan(
        category="application_install",
        executable="builtin:application_installer",
        argv=("stage", "dmg", "org.blender.Blender"),
        approved_paths=(str(artifact), str(destination)),
        rollback_strategy="remove_created_destination",
    )


def test_dmg_mount_failure_attempts_detach_and_cleans_private_stage(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "Blender.dmg"
    artifact.write_bytes(b"fake")
    destination = tmp_path / "Installed.app"
    stage = tmp_path / "private"
    result = ApplicationAdapter(DmgRunner(attach_exit=1), stage).execute(
        application_action(artifact, destination),
        application_plan(artifact, destination),
        timeout=2,
        output_limit=1024,
        cancel=threading.Event(),
    )
    assert not result.success and not result.partial
    assert not destination.exists() and not tuple(stage.iterdir())


def test_application_copy_failure_rolls_back_owned_partial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact = tmp_path / "Blender.dmg"
    artifact.write_bytes(b"fake")
    destination = tmp_path / "Installed.app"

    def fail_copy(source, target, **kwargs):  # type: ignore[no-untyped-def]
        (target / "partial").write_bytes(b"partial")
        raise OSError("fake application copy failure")

    monkeypatch.setattr(adapters.shutil, "copytree", fail_copy)
    result = ApplicationAdapter(DmgRunner(), tmp_path / "private").execute(
        application_action(artifact, destination),
        application_plan(artifact, destination),
        timeout=2,
        output_limit=1024,
        cancel=threading.Event(),
    )
    assert not result.success and not result.partial
    assert result.rollback.succeeded and not destination.exists()


def test_dmg_detach_failure_records_uncertainty_and_rolls_back_copy(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "Blender.dmg"
    artifact.write_bytes(b"fake")
    destination = tmp_path / "Installed.app"
    stage = tmp_path / "private"
    result = ApplicationAdapter(DmgRunner(detach_exit=1), stage).execute(
        application_action(artifact, destination),
        application_plan(artifact, destination),
        timeout=2,
        output_limit=1024,
        cancel=threading.Event(),
    )
    assert not result.success and result.partial
    assert result.rollback.attempted and result.rollback.succeeded is False
    assert result.remaining_human_step
    assert not destination.exists()
    assert tuple(stage.glob("mount-*")), (
        "uncertain mount must not be recursively deleted"
    )


def test_signature_failure_has_no_destination_and_cleans_private_mount(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "Blender.dmg"
    artifact.write_bytes(b"fake")
    destination = tmp_path / "Installed.app"
    stage = tmp_path / "private"
    result = ApplicationAdapter(DmgRunner(verify_exit=1), stage).execute(
        application_action(artifact, destination),
        application_plan(artifact, destination),
        timeout=2,
        output_limit=1024,
        cancel=threading.Event(),
    )
    assert not result.success and not result.partial
    assert not destination.exists() and not tuple(stage.iterdir())
