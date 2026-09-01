"""Focused SSRF and bounds contracts for Phase 5 public ingestion."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pytest

from src import phase5_public_download as downloader


class Response:
    def __init__(
        self, status: int, headers: dict[str, str], chunks: Iterable[bytes] = ()
    ):
        self.status = status
        self.headers = headers
        self._chunks = iter(chunks)
        self.released = False

    def read(self, _amount: int) -> bytes:
        return next(self._chunks, b"")

    def release_conn(self) -> None:
        self.released = True


class Pool:
    def __init__(self, response: Response, calls: list[dict[str, Any]], **kwargs: Any):
        self.response = response
        self.calls = calls
        self.kwargs = kwargs

    def urlopen(self, method: str, target: str, **kwargs: Any) -> Response:
        self.calls.append(
            {"pool": self.kwargs, "method": method, "target": target, "request": kwargs}
        )
        return self.response

    def close(self) -> None:
        pass


def install_network(monkeypatch, dns: dict[str, list[str]], responses: list[Response]):
    calls: list[dict[str, Any]] = []
    resolutions: list[str] = []

    def getaddrinfo(host: str, port: int, **_kwargs: Any):
        resolutions.append(host)
        return [
            (2, 1, 6, "", (address, port))
            for address in dns.get(host, ["93.184.216.34"])
        ]

    def pool_factory(host: str, **kwargs: Any):
        response = responses.pop(0)
        return Pool(response, calls, host=host, **kwargs)

    monkeypatch.setattr(downloader.socket, "getaddrinfo", getaddrinfo)
    monkeypatch.setattr(downloader.urllib3, "HTTPSConnectionPool", pool_factory)
    return calls, resolutions


def test_download_pins_validated_ip_and_preserves_tls_hostname(monkeypatch):
    calls, resolutions = install_network(
        monkeypatch,
        {"docs.example": ["93.184.216.34"]},
        [Response(200, {"Content-Type": "text/html"}, [b"<h1>Guide</h1>"])],
    )

    result = downloader.download_public_document(
        "https://docs.example/guide?edition=owner-secret"
    )

    assert result.body == b"<h1>Guide</h1>"
    assert result.source_type == "public-https"
    assert resolutions == ["docs.example"]
    assert calls[0]["pool"]["host"] == "93.184.216.34"
    assert calls[0]["pool"]["cert_reqs"] == "CERT_REQUIRED"
    assert calls[0]["pool"]["assert_hostname"] == "docs.example"
    assert calls[0]["pool"]["server_hostname"] == "docs.example"
    assert calls[0]["request"]["headers"]["Host"] == "docs.example"
    assert calls[0]["request"]["redirect"] is False
    assert calls[0]["target"] == "/guide?edition=owner-secret"
    assert result.final_url == "https://docs.example/guide"
    assert "owner-secret" not in result.final_url


def test_redirect_is_disabled_and_each_location_is_resolved_again(monkeypatch):
    calls, resolutions = install_network(
        monkeypatch,
        {"first.example": ["93.184.216.34"], "second.example": ["8.8.8.8"]},
        [
            Response(302, {"Location": "https://second.example/final"}),
            Response(200, {"Content-Type": "application/pdf"}, [b"%PDF-safe"]),
        ],
    )

    result = downloader.download_public_document("https://first.example/start")

    assert result.source_type == "public-pdf"
    assert resolutions == ["first.example", "second.example"]
    assert [call["pool"]["host"] for call in calls] == ["93.184.216.34", "8.8.8.8"]
    assert all(call["request"]["redirect"] is False for call in calls)


def test_more_than_five_redirects_is_rejected(monkeypatch):
    responses = [
        Response(302, {"Location": f"https://public.example/hop-{index}"})
        for index in range(downloader.MAX_REDIRECTS + 1)
    ]
    calls, resolutions = install_network(monkeypatch, {}, responses)
    with pytest.raises(downloader.PublicDownloadError):
        downloader.download_public_document("https://public.example/start")
    assert len(calls) == downloader.MAX_REDIRECTS + 1
    assert len(resolutions) == downloader.MAX_REDIRECTS + 1


@pytest.mark.parametrize(
    ("host", "addresses"),
    [
        ("private.example", ["127.0.0.1"]),
        ("mixed.example", ["93.184.216.34", "10.0.0.8"]),
        ("v6.example", ["::1"]),
    ],
)
def test_private_or_mixed_dns_is_rejected_before_connection(
    monkeypatch, host, addresses
):
    calls, _ = install_network(monkeypatch, {host: addresses}, [])

    with pytest.raises(downloader.PublicDownloadError) as error:
        downloader.download_public_document(f"https://{host}/document")

    assert str(error.value) == "public_document_download_failed"
    assert calls == []


@pytest.mark.parametrize(
    "url",
    [
        "http://public.example/file.pdf",
        "https://user:password@public.example/file.pdf",
        "https://localhost/file.pdf",
        "https://public.example:8443/file.pdf",
        "https://public.example/file.pdf#fragment",
    ],
)
def test_invalid_targets_are_sanitized_before_dns(monkeypatch, url):
    monkeypatch.setattr(
        downloader.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no DNS")),
    )
    with pytest.raises(downloader.PublicDownloadError) as error:
        downloader.download_public_document(url)
    assert str(error.value) == "public_document_download_failed"
    assert "password" not in str(error.value)


def test_content_type_and_body_bounds_are_rejected(monkeypatch):
    calls, _ = install_network(
        monkeypatch,
        {},
        [Response(200, {"Content-Type": "application/octet-stream"}, [b"body"])],
    )
    with pytest.raises(downloader.PublicDownloadError):
        downloader.download_public_document("https://public.example/file")
    assert len(calls) == 1

    install_network(
        monkeypatch,
        {},
        [
            Response(
                200,
                {
                    "Content-Type": "text/plain",
                    "Content-Length": str(downloader.MAX_ATTACHMENT_BYTES + 1),
                },
            )
        ],
    )
    with pytest.raises(downloader.PublicDownloadError):
        downloader.download_public_document("https://public.example/large")


def test_streamed_body_and_header_bounds_are_enforced(monkeypatch):
    monkeypatch.setattr(downloader, "MAX_ATTACHMENT_BYTES", 8)
    install_network(
        monkeypatch,
        {},
        [Response(200, {"Content-Type": "text/plain"}, [b"12345678", b"9"])],
    )
    with pytest.raises(downloader.PublicDownloadError):
        downloader.download_public_document("https://public.example/streamed")

    monkeypatch.setattr(downloader, "MAX_RESPONSE_HEADERS", 1)
    install_network(
        monkeypatch,
        {},
        [
            Response(
                200,
                {"Content-Type": "text/plain", "X-Additional": "bounded"},
                [b"ok"],
            )
        ],
    )
    with pytest.raises(downloader.PublicDownloadError):
        downloader.download_public_document("https://public.example/headers")


def test_redirect_to_private_target_never_opens_second_connection(monkeypatch):
    calls, resolutions = install_network(
        monkeypatch,
        {"public.example": ["93.184.216.34"], "internal.example": ["192.168.1.2"]},
        [Response(302, {"Location": "https://internal.example/admin"})],
    )
    with pytest.raises(downloader.PublicDownloadError):
        downloader.download_public_document("https://public.example/start")
    assert resolutions == ["public.example", "internal.example"]
    assert len(calls) == 1
