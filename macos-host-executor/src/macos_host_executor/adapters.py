"""Category-specific adapters. Tests replace these with inert fakes."""

from __future__ import annotations

import hashlib
import ipaddress
import os
import plistlib
import shutil
import socket
import stat
import tarfile
import threading
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urljoin, urlsplit

from .models import (
    ApplicationInstallAction,
    DownloadAction,
    HomebrewAction,
    HostInspectionAction,
    Mutation,
    NativeApplicationAction,
    ProcessSummary,
    RollbackReport,
)
from .policy import ExecutionPlan
from .runner import SubprocessRunner
from .security import redact

MAX_ARCHIVE_MEMBERS = 10_000
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 2_147_483_648
MAX_NATIVE_OUTPUT_BYTES = 2_147_483_648
MAX_CONTENT_LENGTH_DIGITS = 19


@dataclass(frozen=True)
class AdapterResult:
    success: bool
    verified: bool
    process: ProcessSummary = ProcessSummary()
    observed_paths: tuple[str, ...] = ()
    mutations: tuple[Mutation, ...] = ()
    rollback: RollbackReport = RollbackReport()
    partial: bool = False
    message: str = ""
    remaining_human_step: str | None = None


class ActionAdapter(Protocol):
    def execute(
        self,
        action: object,
        plan: ExecutionPlan,
        *,
        timeout: int,
        output_limit: int,
        cancel: threading.Event,
    ) -> AdapterResult: ...


class InspectionAdapter:
    def __init__(self, runner: SubprocessRunner):
        self.runner = runner

    def execute(
        self,
        action: HostInspectionAction,
        plan: ExecutionPlan,
        *,
        timeout: int,
        output_limit: int,
        cancel: threading.Event,
    ) -> AdapterResult:
        if action.query in {"macos_version", "architecture"}:
            run = self.runner.run(
                plan.argv,
                cwd=None,
                timeout_seconds=timeout,
                output_limit_bytes=output_limit,
                cancel=cancel,
            )
            summary = _summary(run, output_limit)
            return AdapterResult(
                success=run.exit_code == 0,
                verified=run.exit_code == 0,
                process=summary,
                message=summary.stdout,
            )
        path = Path(plan.approved_paths[0])
        if action.query == "disk_space":
            values = os.statvfs(path)
            message = f"available_bytes={values.f_bavail * values.f_frsize}"
        elif action.query == "path_metadata":
            values = path.stat()
            message = f"kind={'directory' if stat.S_ISDIR(values.st_mode) else 'file'} size={values.st_size}"
        elif action.query == "application_presence":
            message = "present=true"
        else:
            plist = path / "Contents" / "Info.plist"
            with plist.open("rb") as handle:
                info = plistlib.load(handle)
            message = f"version={info.get('CFBundleShortVersionString', 'unknown')}"
        return AdapterResult(
            success=True, verified=True, observed_paths=(str(path),), message=message
        )


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req: object, fp: object, code: int, msg: str, headers: object, newurl: str
    ) -> None:
        return None


class DownloadAdapter:
    def __init__(self, staging_directory: Path, allowed_domains: tuple[str, ...]):
        self.staging_directory = staging_directory
        self.allowed_domains = {value.lower() for value in allowed_domains}
        # Environment proxy variables must never redirect this privileged fetcher.
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), _NoRedirect
        )

    def execute(
        self,
        action: DownloadAction,
        plan: ExecutionPlan,
        *,
        timeout: int,
        output_limit: int,
        cancel: threading.Event,
    ) -> AdapterResult:
        stage = (
            self.staging_directory
            / f"{hashlib.sha256(action.url.encode()).hexdigest()}.part"
        )
        stage.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        url = action.url
        redirects = 0
        digest = hashlib.sha256()
        total = 0
        destination = Path(plan.approved_paths[0])
        destination_created = False
        destination_identity: tuple[int, int] | None = None
        mutation = Mutation(
            operation="create", path=str(destination), detail="verified download"
        )
        try:
            while True:
                _validate_download_url(url, self.allowed_domains)
                _resolve_public_https_host(url)
                request = urllib.request.Request(
                    url, method="GET", headers={"User-Agent": "macos-host-executor/1"}
                )
                try:
                    response = self.opener.open(request, timeout=timeout)
                    break
                except urllib.error.HTTPError as exc:
                    if (
                        exc.code not in {301, 302, 303, 307, 308}
                        or redirects >= action.redirect_limit
                    ):
                        exc.close()
                        raise
                    location = exc.headers.get("Location")
                    exc.close()
                    if not location:
                        raise ValueError("redirect has no Location") from exc
                    redirected = _validated_redirect(url, location)
                    _validate_download_url(redirected, self.allowed_domains)
                    url = redirected
                    redirects += 1
            with response:
                _validate_download_response(response, url)
                length = _bounded_content_length(
                    response.headers.get("Content-Length"), maximum=action.max_bytes
                )
                if length is not None and length > action.max_bytes:
                    raise ValueError("download exceeds declared size")
                descriptor = os.open(stage, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, "wb") as output:
                    while chunk := response.read(64 * 1024):
                        if cancel.is_set():
                            raise InterruptedError("cancelled")
                        total += len(chunk)
                        if total > action.max_bytes:
                            raise ValueError("download exceeds declared size")
                        digest.update(chunk)
                        output.write(chunk)
                    output.flush()
                    os.fsync(output.fileno())
            if digest.hexdigest() != action.sha256:
                raise ValueError("download checksum mismatch")
            _verify_archive(stage, action.archive)
            with stage.open("rb") as source:
                descriptor = os.open(
                    destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
                )
                destination_created = True
                destination_info = os.fstat(descriptor)
                destination_identity = (
                    destination_info.st_dev,
                    destination_info.st_ino,
                )
                with os.fdopen(descriptor, "wb") as output:
                    shutil.copyfileobj(source, output)
                    output.flush()
                    os.fsync(output.fileno())
            if not _is_owned_regular_file(destination, destination_identity, total):
                raise ValueError("download destination identity changed during copy")
            return AdapterResult(
                success=True,
                verified=True,
                observed_paths=(str(destination),),
                mutations=(mutation,),
                message=f"downloaded_bytes={total} redirects={redirects}",
            )
        except Exception as exc:
            rollback = RollbackReport()
            partial = destination_created
            if destination_created:
                removed = _unlink_owned_regular(destination, destination_identity)
                rollback = RollbackReport(
                    attempted=True,
                    succeeded=removed,
                    detail=(
                        "removed request-created partial destination"
                        if removed
                        else "partial destination ownership changed or removal failed; inspect manually"
                    ),
                )
                partial = os.path.lexists(destination)
            return AdapterResult(
                success=False,
                verified=False,
                observed_paths=(str(destination),) if destination_created else (),
                mutations=(mutation,) if destination_created else (),
                rollback=rollback,
                partial=partial,
                message=str(exc),
            )
        finally:
            stage.unlink(missing_ok=True)


def _validate_download_url(url: str, allowed_domains: set[str]) -> None:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or "\\" in url
        or any(ord(character) < 0x20 or ord(character) == 0x7F for character in url)
        or parsed.hostname.lower() not in allowed_domains
    ):
        raise ValueError(
            "download hop must be an exact allowlisted credential-free HTTPS URL "
            "without query or fragment"
        )


def _resolve_public_https_host(url: str) -> None:
    parsed = urlsplit(url)
    host = parsed.hostname
    if not host:
        raise ValueError("download host is missing")
    try:
        port = parsed.port or 443
        answers = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ValueError("download host could not be resolved") from exc
    addresses = {answer[4][0].split("%", 1)[0] for answer in answers}
    if not addresses:
        raise ValueError("download host resolved to no addresses")
    for value in addresses:
        try:
            address = ipaddress.ip_address(value)
        except ValueError as exc:
            raise ValueError("download host resolved to an invalid address") from exc
        if (
            address.is_loopback
            or address.is_private
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
            or address.is_unspecified
            or not address.is_global
        ):
            raise ValueError("download host resolved to a non-public address")


def _validated_redirect(current_url: str, location: str) -> str:
    if (
        location != location.strip()
        or any(
            ord(character) < 0x20 or ord(character) == 0x7F for character in location
        )
        or "\\" in location
    ):
        raise ValueError("redirect Location is invalid")
    redirected = urljoin(current_url, location)
    if not redirected:
        raise ValueError("redirect Location is invalid")
    return redirected


def _validate_download_response(response: object, requested_url: str) -> None:
    status = response.getcode()
    if status != 200:
        response.close()
        raise ValueError("download response must be HTTP 200")
    final_url = response.geturl()
    if final_url != requested_url:
        response.close()
        raise ValueError("downloader followed an unvalidated redirect")


def _bounded_content_length(
    value: str | None, *, maximum: int | None = None
) -> int | None:
    if value is None:
        return None
    if (
        not value
        or len(value) > MAX_CONTENT_LENGTH_DIGITS
        or not value.isascii()
        or not value.isdecimal()
    ):
        raise ValueError("invalid or unbounded Content-Length")
    if maximum is not None and len(value.lstrip("0") or "0") > len(str(maximum)):
        raise ValueError("download exceeds declared size")
    return int(value)


def _is_owned_regular_file(
    path: Path, identity: tuple[int, int] | None, expected_size: int | None = None
) -> bool:
    if identity is None:
        return False
    try:
        info = path.lstat()
    except OSError:
        return False
    return (
        stat.S_ISREG(info.st_mode)
        and (info.st_dev, info.st_ino) == identity
        and (expected_size is None or info.st_size == expected_size)
    )


def _unlink_owned_regular(path: Path, identity: tuple[int, int] | None) -> bool:
    if not _is_owned_regular_file(path, identity):
        return False
    try:
        path.unlink()
    except OSError:
        return False
    return not os.path.lexists(path)


def _is_owned_directory(path: Path, identity: tuple[int, int] | None) -> bool:
    if identity is None:
        return False
    try:
        info = path.lstat()
    except OSError:
        return False
    return stat.S_ISDIR(info.st_mode) and (info.st_dev, info.st_ino) == identity


def _remove_owned_directory(path: Path, identity: tuple[int, int] | None) -> bool:
    if not _is_owned_directory(path, identity):
        return False
    try:
        shutil.rmtree(path)
    except OSError:
        return False
    return not os.path.lexists(path)


class HomebrewAdapter:
    def __init__(self, runner: SubprocessRunner):
        self.runner = runner

    def execute(
        self,
        action: HomebrewAction,
        plan: ExecutionPlan,
        *,
        timeout: int,
        output_limit: int,
        cancel: threading.Event,
    ) -> AdapterResult:
        run = self.runner.run(
            plan.argv,
            cwd=None,
            timeout_seconds=timeout,
            output_limit_bytes=output_limit,
            cancel=cancel,
        )
        process = _summary(run, output_limit)
        if run.exit_code != 0:
            return AdapterResult(
                success=False,
                verified=False,
                process=process,
                message="Homebrew operation failed",
            )
        flag = "--formula" if action.package_kind == "formula" else "--cask"
        verification = self.runner.run(
            (plan.executable, "list", flag, action.package),
            cwd=None,
            timeout_seconds=min(timeout, 60),
            output_limit_bytes=output_limit,
            cancel=cancel,
        )
        verified = (
            verification.exit_code == 0
            if action.operation == "install"
            else verification.exit_code != 0
        )
        return AdapterResult(
            success=True,
            verified=verified,
            process=process,
            message="exact Homebrew outcome verified"
            if verified
            else "Homebrew outcome could not be verified",
        )


class ApplicationAdapter:
    """Fixed DMG/ZIP mechanics; never invokes installer, sudo, open, or GUI automation."""

    def __init__(self, runner: SubprocessRunner, staging_directory: Path):
        self.runner = runner
        self.staging_directory = staging_directory
        self.staging_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.staging_directory, 0o700)

    def execute(
        self,
        action: ApplicationInstallAction,
        plan: ExecutionPlan,
        *,
        timeout: int,
        output_limit: int,
        cancel: threading.Event,
    ) -> AdapterResult:
        artifact, destination = map(Path, plan.approved_paths)
        suffix = hashlib.sha256(str(artifact).encode()).hexdigest()[:12]
        mount = self.staging_directory / f"mount-{suffix}"
        extract = self.staging_directory / f"extract-{suffix}"
        attach_attempted = False
        destination_created = False
        destination_identity: tuple[int, int] | None = None
        detach_failed = False
        cleanup_failed = False
        error: Exception | None = None
        process = ProcessSummary()
        mutation = Mutation(
            operation="create",
            path=str(destination),
            detail="verified application copy",
        )
        try:
            if action.artifact_kind == "dmg":
                mount.mkdir(mode=0o700)
                attach_attempted = True
                attach = self.runner.run(
                    (
                        "/usr/bin/hdiutil",
                        "attach",
                        "-nobrowse",
                        "-readonly",
                        "-mountpoint",
                        str(mount),
                        str(artifact),
                    ),
                    cwd=None,
                    timeout_seconds=timeout,
                    output_limit_bytes=output_limit,
                    cancel=cancel,
                )
                process = _summary(attach, output_limit)
                if attach.exit_code != 0:
                    raise ValueError("DMG attach failed")
                candidates = tuple(mount.glob("*.app"))
            else:
                extract.mkdir(mode=0o700)
                with zipfile.ZipFile(artifact) as archive:
                    _safe_zip_extract(archive, extract)
                candidates = tuple(extract.glob("*.app"))
            if len(candidates) != 1:
                raise ValueError(
                    "artifact must contain exactly one top-level application"
                )
            source_app = candidates[0]
            verify = self.runner.run(
                (
                    "/usr/bin/codesign",
                    "--verify",
                    "--deep",
                    "--strict",
                    str(source_app),
                ),
                cwd=None,
                timeout_seconds=timeout,
                output_limit_bytes=output_limit,
                cancel=cancel,
            )
            identity = self.runner.run(
                ("/usr/bin/codesign", "-dv", "--verbose=4", str(source_app)),
                cwd=None,
                timeout_seconds=timeout,
                output_limit_bytes=output_limit,
                cancel=cancel,
            )
            identity_text = f"{identity.stdout}\n{identity.stderr}"
            team_matches = tuple(
                line.split("=", 1)[1].strip()
                for line in identity_text.splitlines()
                if line.startswith("TeamIdentifier=")
            )
            assess = self.runner.run(
                ("/usr/sbin/spctl", "--assess", "--type", "execute", str(source_app)),
                cwd=None,
                timeout_seconds=timeout,
                output_limit_bytes=output_limit,
                cancel=cancel,
            )
            if (
                verify.exit_code != 0
                or identity.exit_code != 0
                or team_matches != (action.require_team_id,)
                or (action.require_notarization and assess.exit_code != 0)
            ):
                raise ValueError(
                    "signature identity, team ID, or notarization assessment failed"
                )
            # Creating the root ourselves gives rollback an inode identity to verify
            # before removing a request-created partial copy.
            destination.mkdir(mode=0o700)
            destination_created = True
            destination_info = destination.lstat()
            destination_identity = (destination_info.st_dev, destination_info.st_ino)
            shutil.copytree(source_app, destination, symlinks=False, dirs_exist_ok=True)
        except Exception as exc:
            error = exc
        finally:
            if attach_attempted:
                try:
                    detach = self.runner.run(
                        ("/usr/bin/hdiutil", "detach", str(mount)),
                        cwd=None,
                        timeout_seconds=min(timeout, 30),
                        output_limit_bytes=output_limit,
                        cancel=threading.Event(),
                    )
                    if detach.exit_code != 0:
                        detach_failed = True
                        if error is None:
                            error = ValueError(
                                "DMG detach failed after application copy"
                            )
                except Exception as exc:
                    detach_failed = True
                    if error is None:
                        error = ValueError("DMG detach outcome is uncertain")
                    error.add_note(str(exc))
            for private_path in (extract, mount if not detach_failed else None):
                if private_path is None or not private_path.exists():
                    continue
                try:
                    shutil.rmtree(private_path)
                except OSError:
                    cleanup_failed = True
                    if error is None:
                        error = ValueError("private application staging cleanup failed")

        if error is None and not _is_owned_directory(destination, destination_identity):
            error = ValueError("application destination identity changed during copy")
        if error is None:
            return AdapterResult(
                True,
                True,
                process=process,
                observed_paths=(str(destination),),
                mutations=(mutation,),
                message="application staged"
                if action.mode == "stage"
                else "application installed",
            )

        rollback = RollbackReport()
        destination_remaining = destination_created and os.path.lexists(destination)
        if (
            destination_created
            and plan.rollback_strategy == "remove_created_destination"
        ):
            removed = _remove_owned_directory(destination, destination_identity)
            destination_remaining = os.path.lexists(destination)
            rollback_succeeded = removed and not detach_failed and not cleanup_failed
            rollback = RollbackReport(
                attempted=True,
                succeeded=rollback_succeeded,
                detail=(
                    "removed request-created destination"
                    if rollback_succeeded
                    else "destination ownership/removal, detach, or private cleanup remains uncertain"
                ),
            )
        elif detach_failed or cleanup_failed:
            rollback = RollbackReport(
                attempted=attach_attempted,
                succeeded=False,
                detail="DMG detach or private staging cleanup remains uncertain",
            )
        partial = destination_remaining or detach_failed or cleanup_failed
        human_step = (
            "Inspect the declared destination and private mount/staging paths."
            if partial
            else None
        )
        return AdapterResult(
            False,
            False,
            process=process,
            observed_paths=(str(destination),) if destination_created else (),
            mutations=(mutation,) if destination_created else (),
            rollback=rollback,
            partial=partial,
            message=str(error),
            remaining_human_step=human_step,
        )


class NativeApplicationAdapter:
    def __init__(self, runner: SubprocessRunner):
        self.runner = runner

    def execute(
        self,
        action: NativeApplicationAction,
        plan: ExecutionPlan,
        *,
        timeout: int,
        output_limit: int,
        cancel: threading.Event,
    ) -> AdapterResult:
        output = (
            Path(plan.approved_paths[-1])
            if action.operation == "blender_background_render"
            else None
        )
        if output is not None and os.path.lexists(output):
            return AdapterResult(
                False,
                False,
                message="approved output was not absent immediately before execution",
            )
        run = self.runner.run(
            plan.argv,
            cwd=plan.working_directory,
            timeout_seconds=timeout,
            output_limit_bytes=output_limit,
            cancel=cancel,
        )
        process = _summary(run, output_limit)
        output_exists = bool(output is not None and os.path.lexists(output))
        output_regular = False
        output_size: int | None = None
        if output_exists and output is not None:
            try:
                info = output.lstat()
                output_regular = stat.S_ISREG(info.st_mode)
                output_size = info.st_size
            except OSError:
                output_regular = False
        output_verified = (
            output_regular
            and output_size is not None
            and 0 < output_size <= MAX_NATIVE_OUTPUT_BYTES
        )
        verified = run.exit_code == 0 and (
            action.operation == "blender_version" or output_verified
        )
        mutations: tuple[Mutation, ...] = ()
        if output_exists and action.output_path:
            mutations = (
                Mutation(
                    operation="create",
                    path=action.output_path,
                    detail="native application output",
                ),
            )
        return AdapterResult(
            run.exit_code == 0,
            verified,
            process=process,
            observed_paths=(action.output_path,)
            if output_exists and action.output_path
            else (),
            mutations=mutations,
            partial=bool(output_exists and not verified),
            message="native application outcome verified"
            if verified
            else "native application output is absent, non-regular, oversized, or the process failed",
        )


def _summary(run: object, limit: int) -> ProcessSummary:
    return ProcessSummary(
        pid=run.pid,
        exit_code=run.exit_code,
        stdout=redact(run.stdout, home=str(Path.home()), limit=limit),
        stderr=redact(run.stderr, home=str(Path.home()), limit=limit),
        output_truncated=run.output_truncated,
        timed_out=run.timed_out,
        cancelled=run.cancelled,
    )


def _verify_archive(path: Path, kind: str) -> None:
    if kind == "zip":
        try:
            with zipfile.ZipFile(path) as archive:
                _inspect_zip_members(archive, Path("/private/archive-validation"))
        except (OSError, zipfile.BadZipFile) as exc:
            raise ValueError("invalid ZIP archive") from exc
    if kind == "tar_gz":
        try:
            with tarfile.open(path, mode="r:gz") as archive:
                total = 0
                for count, member in enumerate(archive, start=1):
                    if count > MAX_ARCHIVE_MEMBERS:
                        raise ValueError("archive member count exceeds limit")
                    target = Path(member.name)
                    if target.is_absolute() or ".." in target.parts:
                        raise ValueError("archive path traversal denied")
                    if not (member.isfile() or member.isdir()):
                        raise ValueError(
                            "archive links, devices, FIFOs, and special types are denied"
                        )
                    if member.size < 0:
                        raise ValueError("archive member has an invalid size")
                    total += member.size
                    if total > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                        raise ValueError("archive uncompressed size exceeds limit")
        except tarfile.TarError as exc:
            raise ValueError("invalid gzip tar archive") from exc
    if kind == "dmg":
        with path.open("rb") as handle:
            prefix = handle.read(4)
            handle.seek(max(0, path.stat().st_size - 512))
            trailer = handle.read(512)
        if prefix not in {b"koly", b"xar!"} and b"koly" not in trailer:
            raise ValueError("invalid DMG container marker")


def _inspect_zip_members(
    archive: zipfile.ZipFile, destination: Path
) -> tuple[tuple[zipfile.ZipInfo, Path], ...]:
    inspected: list[tuple[zipfile.ZipInfo, Path]] = []
    total = 0
    root = destination.resolve()
    for count, member in enumerate(archive.infolist(), start=1):
        if count > MAX_ARCHIVE_MEMBERS:
            raise ValueError("archive member count exceeds limit")
        target = (destination / member.filename).resolve()
        if root not in target.parents and target != root:
            raise ValueError("archive path traversal denied")
        member_type = stat.S_IFMT(member.external_attr >> 16)
        allowed_types = {0, stat.S_IFDIR} if member.is_dir() else {0, stat.S_IFREG}
        if member_type not in allowed_types:
            raise ValueError("ZIP links, devices, FIFOs, and special types are denied")
        if member.file_size < 0:
            raise ValueError("archive member has an invalid size")
        total += member.file_size
        if total > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
            raise ValueError("archive uncompressed size exceeds limit")
        inspected.append((member, target))
    return tuple(inspected)


def _safe_zip_extract(archive: zipfile.ZipFile, destination: Path) -> None:
    try:
        members = _inspect_zip_members(archive, destination)
        for member, target in members:
            if member.is_dir():
                target.mkdir(mode=0o700, parents=True, exist_ok=True)
                continue
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with archive.open(member) as source, target.open("xb") as output:
                copied = 0
                while chunk := source.read(64 * 1024):
                    copied += len(chunk)
                    if copied > member.file_size:
                        raise ValueError("ZIP member exceeded its declared size")
                    output.write(chunk)
                if copied != member.file_size:
                    raise ValueError("ZIP member size did not match its declaration")
    except Exception:
        # Extraction is private staging. Never retain attacker-controlled partials.
        shutil.rmtree(destination, ignore_errors=True)
        raise
