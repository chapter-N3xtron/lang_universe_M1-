import io
import zipfile

import pytest

from src.epub_attachments import EpubAttachmentError, extract_epub


def _epub(*, unsafe_path: bool = False, encrypted_manifest: bool = False) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr(
            "META-INF/container.xml",
            """<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
            <rootfiles><rootfile full-path="OPS/book.opf"/></rootfiles>
            </container>""",
        )
        archive.writestr(
            "OPS/book.opf",
            """<package xmlns="http://www.idpf.org/2007/opf">
            <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
              <dc:title>Selected Book</dc:title><dc:creator>Human Author</dc:creator>
            </metadata>
            <manifest><item id="chapter" href="chapter.xhtml"
              media-type="application/xhtml+xml"/></manifest>
            <spine><itemref idref="chapter"/></spine>
            </package>""",
        )
        archive.writestr(
            "OPS/chapter.xhtml",
            "<html><body><h1>Opening</h1><p>Only this selected book is read.</p>"
            "<script>ignored()</script></body></html>",
        )
        if unsafe_path:
            archive.writestr("../outside.txt", "not allowed")
        if encrypted_manifest:
            archive.writestr("META-INF/encryption.xml", "<encryption/>")
    return buffer.getvalue()


def test_extract_epub_returns_bounded_structured_publication_text():
    result = extract_epub(_epub(), "/Users/example/Selected Book.epub")

    assert result["filename"] == "Selected Book.epub"
    assert result["title"] == "Selected Book"
    assert result["author"] == "Human Author"
    assert "Only this selected book is read." in result["text"]
    assert "ignored()" not in result["text"]
    assert result["chapters"][0]["source"] == "OPS/chapter.xhtml"
    assert result["content_profile"]["textual"] is True


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (_epub(unsafe_path=True), "unsafe archive path"),
        (_epub(encrypted_manifest=True), "Encrypted or obfuscated"),
        (b"not an epub", "not a valid EPUB"),
    ],
)
def test_extract_epub_rejects_unsafe_or_invalid_containers(payload, message):
    with pytest.raises(EpubAttachmentError, match=message):
        extract_epub(payload, "book.epub")
