"""Bounded, IP-pinned downloader for explicit owner public-document ingestion."""

from __future__ import annotations

import ipaddress
import socket
from contextlib import suppress
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit, urlunsplit

import urllib3

from src.document_attachments import MAX_ATTACHMENT_BYTES

MAX_PUBLIC_URL_BYTES = 4096
MAX_REDIRECTS = 5
MAX_RESPONSE_HEADERS = 100
MAX_RESPONSE_HEADER_BYTES = 64 * 1024
_CONNECT_TIMEOUT_SECONDS = 5.0
_READ_TIMEOUT_SECONDS = 15.0
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_CONTENT_EXTENSIONS = {
    "application/pdf": ("public-pdf", ".pdf"),
    "text/html": ("public-https", ".html"),
    "application/xhtml+xml": ("public-https", ".html"),
    "text/plain": ("public-https", ".txt"),
}


class PublicDownloadError(ValueError):
    """A deliberately context-free public download failure."""


@dataclass(frozen=True)
class PublicDownload:
    body: bytes
    final_url: str
    content_type: str
    source_type: str
    extension: str


def _fail() -> PublicDownloadError:
    return PublicDownloadError("public_document_download_failed")


def _validated_target(url: str) -> tuple[str, str, int, str]:
    if (
        type(url) is not str
        or not url
        or len(url.encode("utf-8")) > MAX_PUBLIC_URL_BYTES
        or any(ord(character) < 32 or ord(character) == 127 for character in url)
    ):
        raise _fail()
    try:
        parsed = urlsplit(url)
        port = parsed.port or 443
    except (UnicodeError, ValueError):
        raise _fail() from None
    if (
        parsed.scheme.casefold() != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or port != 443
    ):
        raise _fail()
    try:
        hostname = parsed.hostname.rstrip(".").encode("idna").decode("ascii").casefold()
    except UnicodeError:
        raise _fail() from None
    if (
        not hostname
        or hostname
        in {
            "localhost",
            "localhost.localdomain",
            "ip6-localhost",
        }
        or hostname.endswith((".local", ".localhost", ".internal", ".home", ".lan"))
    ):
        raise _fail()
    # Normalize only scheme/host casing. The path and query remain provenance and are
    # never included in downloader errors or logs.
    display_host = f"[{hostname}]" if ":" in hostname else hostname
    normalized = urlunsplit(
        ("https", display_host, parsed.path or "/", parsed.query, "")
    )
    return normalized, hostname, port, parsed.path or "/"


def _resolve_global(hostname: str, port: int) -> tuple[str, ...]:
    try:
        records = socket.getaddrinfo(
            hostname,
            port,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
        addresses = tuple(dict.fromkeys(record[4][0] for record in records))
        parsed = tuple(ipaddress.ip_address(address) for address in addresses)
    except (OSError, ValueError):
        raise _fail() from None
    if not parsed or any(not address.is_global for address in parsed):
        raise _fail()
    return tuple(str(address) for address in parsed)


def _validate_headers(response: urllib3.response.BaseHTTPResponse) -> None:
    headers = list(response.headers.items())
    if len(headers) > MAX_RESPONSE_HEADERS:
        raise _fail()
    total = sum(
        len(str(name).encode("utf-8")) + len(str(value).encode("utf-8")) + 4
        for name, value in headers
    )
    if total > MAX_RESPONSE_HEADER_BYTES:
        raise _fail()


def download_public_document(url: str) -> PublicDownload:
    """Download one validated HTTPS resource without proxies or implicit redirects.

    Each hop gets fresh DNS validation and a fresh pool connected to the selected
    validated address. ``server_hostname``/``assert_hostname`` retain TLS SNI and
    certificate verification for the URL hostname while ``Host`` retains HTTP routing.
    """

    current = url
    for redirects in range(MAX_REDIRECTS + 1):
        normalized, hostname, port, _ = _validated_target(current)
        addresses = _resolve_global(hostname, port)
        pinned_ip = addresses[0]
        host_header = f"[{hostname}]" if ":" in hostname else hostname
        pool = urllib3.HTTPSConnectionPool(
            pinned_ip,
            port=port,
            maxsize=1,
            block=True,
            retries=False,
            timeout=urllib3.Timeout(
                connect=_CONNECT_TIMEOUT_SECONDS,
                read=_READ_TIMEOUT_SECONDS,
            ),
            cert_reqs="CERT_REQUIRED",
            assert_hostname=hostname,
            server_hostname=hostname,
        )
        response = None
        try:
            target = urlsplit(normalized)
            request_target = urlunsplit(("", "", target.path or "/", target.query, ""))
            response = pool.urlopen(
                "GET",
                request_target,
                headers={
                    "Host": host_header,
                    "User-Agent": "InstallationLibraryPublicIngest/1",
                    "Accept": "application/pdf,text/html,text/plain,application/xhtml+xml",
                    "Accept-Encoding": "identity",
                },
                redirect=False,
                preload_content=False,
                decode_content=False,
                retries=False,
            )
            _validate_headers(response)
            if response.status in _REDIRECT_STATUSES:
                location = response.headers.get("Location")
                if redirects >= MAX_REDIRECTS or not location:
                    raise _fail()
                try:
                    candidate = urljoin(normalized, location)
                except ValueError:
                    raise _fail() from None
                _validated_target(candidate)
                current = candidate
                continue
            if response.status != 200:
                raise _fail()
            content_encoding = response.headers.get("Content-Encoding", "identity")
            if content_encoding.strip().casefold() != "identity":
                raise _fail()
            media_type = (
                response.headers.get("Content-Type", "")
                .split(";", 1)[0]
                .strip()
                .casefold()
            )
            content = _CONTENT_EXTENSIONS.get(media_type)
            if content is None:
                raise _fail()
            length = response.headers.get("Content-Length")
            if length is not None:
                try:
                    declared = int(length)
                except ValueError:
                    raise _fail() from None
                if declared < 0 or declared > MAX_ATTACHMENT_BYTES:
                    raise _fail()
            body = bytearray()
            while True:
                chunk = response.read(
                    min(64 * 1024, MAX_ATTACHMENT_BYTES + 1 - len(body))
                )
                if not chunk:
                    break
                body.extend(chunk)
                if len(body) > MAX_ATTACHMENT_BYTES:
                    raise _fail()
            if not body:
                raise _fail()
            source_type, extension = content
            provenance_url = urlunsplit(
                ("https", host_header, target.path or "/", "", "")
            )
            return PublicDownload(
                body=bytes(body),
                final_url=provenance_url,
                content_type=media_type,
                source_type=source_type,
                extension=extension,
            )
        except PublicDownloadError:
            raise
        except Exception:
            raise _fail() from None
        finally:
            if response is not None:
                with suppress(Exception):
                    response.release_conn()
            with suppress(Exception):
                pool.close()
    raise _fail()
