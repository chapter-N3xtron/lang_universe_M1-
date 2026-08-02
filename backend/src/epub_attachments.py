"""Bounded, read-only extraction for explicitly uploaded EPUB attachments."""

from __future__ import annotations

import io
import posixpath
import zipfile
from html.parser import HTMLParser
from pathlib import PurePosixPath
from urllib.parse import unquote
from xml.etree import ElementTree


MAX_EPUB_BYTES = 25 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 2_000
MAX_EXPANDED_BYTES = 100 * 1024 * 1024
MAX_ENTRY_BYTES = 8 * 1024 * 1024
MAX_TEXT_CHARACTERS = 200_000


class EpubAttachmentError(ValueError):
    """A recoverable validation failure for a selected EPUB."""


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _safe_xml(data: bytes) -> ElementTree.Element:
    upper = data[:4096].upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise EpubAttachmentError("EPUB XML declarations are not supported")
    try:
        return ElementTree.fromstring(data)
    except ElementTree.ParseError as exc:
        raise EpubAttachmentError("EPUB metadata is malformed") from exc


def _safe_archive_path(raw_path: str) -> str:
    path = unquote(raw_path).replace("\\", "/")
    parts = PurePosixPath(path).parts
    if not path or path.startswith("/") or ".." in parts:
        raise EpubAttachmentError("EPUB contains an unsafe archive path")
    return posixpath.normpath(path)


class _PublicationText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignored_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        del attrs
        if tag in {"script", "style", "noscript"}:
            self._ignored_depth += 1
        elif not self._ignored_depth and tag in {
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "p",
            "div",
            "li",
            "blockquote",
            "br",
        }:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._ignored_depth:
            self._ignored_depth -= 1
        elif not self._ignored_depth and tag in {
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "p",
            "div",
            "li",
            "blockquote",
        }:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            cleaned = " ".join(data.split())
            if cleaned:
                self._parts.extend((cleaned, " "))

    def text(self) -> str:
        lines = (" ".join(line.split()) for line in "".join(self._parts).splitlines())
        return "\n".join(line for line in lines if line)


def _read_entry(archive: zipfile.ZipFile, name: str) -> bytes:
    safe_name = _safe_archive_path(name)
    try:
        info = archive.getinfo(safe_name)
    except KeyError as exc:
        raise EpubAttachmentError("EPUB references a missing publication file") from exc
    if info.file_size > MAX_ENTRY_BYTES:
        raise EpubAttachmentError("An EPUB publication entry is too large")
    return archive.read(info)


def _metadata_text(root: ElementTree.Element, name: str) -> str:
    for element in root.iter():
        if _local_name(element.tag) == name and element.text:
            return " ".join(element.text.split())
    return ""


def extract_epub(data: bytes, filename: str) -> dict:
    """Validate an EPUB container and return bounded publication text and metadata."""

    if len(data) > MAX_EPUB_BYTES:
        raise EpubAttachmentError("EPUB exceeds the 25 MB upload limit")
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise EpubAttachmentError("The selected file is not a valid EPUB container") from exc

    with archive:
        entries = archive.infolist()
        if len(entries) > MAX_ARCHIVE_ENTRIES:
            raise EpubAttachmentError("EPUB contains too many archive entries")
        if sum(entry.file_size for entry in entries) > MAX_EXPANDED_BYTES:
            raise EpubAttachmentError("EPUB expanded size exceeds the safety limit")
        for entry in entries:
            _safe_archive_path(entry.filename)
            if entry.flag_bits & 0x1:
                raise EpubAttachmentError("Encrypted EPUB content is not supported")

        mimetype = _read_entry(archive, "mimetype").decode("ascii", errors="replace").strip()
        if mimetype != "application/epub+zip":
            raise EpubAttachmentError("The selected archive is not identified as an EPUB")
        if "META-INF/encryption.xml" in archive.namelist():
            raise EpubAttachmentError("Encrypted or obfuscated EPUB content is not supported")

        container = _safe_xml(_read_entry(archive, "META-INF/container.xml"))
        package_path = next(
            (
                element.attrib.get("full-path", "")
                for element in container.iter()
                if _local_name(element.tag) == "rootfile"
            ),
            "",
        )
        package_path = _safe_archive_path(package_path)
        package = _safe_xml(_read_entry(archive, package_path))
        package_dir = posixpath.dirname(package_path)

        manifest: dict[str, tuple[str, str]] = {}
        spine: list[str] = []
        image_count = 0
        media_overlay = False
        for element in package.iter():
            local = _local_name(element.tag)
            if local == "item":
                item_id = element.attrib.get("id", "")
                href = element.attrib.get("href", "")
                media_type = element.attrib.get("media-type", "")
                if item_id and href:
                    archive_path = _safe_archive_path(posixpath.join(package_dir, href))
                    manifest[item_id] = (archive_path, media_type)
                    image_count += int(media_type.startswith("image/"))
                    media_overlay = media_overlay or bool(element.attrib.get("media-overlay"))
            elif local == "itemref" and element.attrib.get("idref"):
                spine.append(element.attrib["idref"])

        publication_items = [
            manifest[item_id]
            for item_id in spine
            if item_id in manifest
            and manifest[item_id][1] in {"application/xhtml+xml", "text/html"}
        ]
        if not publication_items:
            publication_items = [
                item
                for item in manifest.values()
                if item[1] in {"application/xhtml+xml", "text/html"}
            ]

        chapters: list[dict[str, object]] = []
        text_parts: list[str] = []
        remaining = MAX_TEXT_CHARACTERS
        truncated = False
        for index, (chapter_path, _media_type) in enumerate(publication_items, start=1):
            parser = _PublicationText()
            parser.feed(_read_entry(archive, chapter_path).decode("utf-8", errors="replace"))
            chapter_text = parser.text()
            if not chapter_text:
                continue
            accepted = chapter_text[:remaining]
            chapters.append(
                {
                    "index": index,
                    "source": chapter_path,
                    "characters": len(chapter_text),
                }
            )
            text_parts.append(f"## Chapter {index} [{chapter_path}]\n\n{accepted}")
            remaining -= len(accepted)
            if remaining <= 0:
                truncated = index < len(publication_items) or len(accepted) < len(chapter_text)
                break

        return {
            "filename": PurePosixPath(filename).name,
            "title": _metadata_text(package, "title") or PurePosixPath(filename).stem,
            "author": _metadata_text(package, "creator"),
            "text": "\n\n".join(text_parts),
            "chapters": chapters,
            "truncated": truncated,
            "content_profile": {
                "textual": bool(text_parts),
                "fixed_layout": any(
                    element.attrib.get("property") == "rendition:layout"
                    and (element.text or "").strip() == "pre-paginated"
                    for element in package.iter()
                ),
                "images": image_count,
                "media_overlays": media_overlay,
            },
        }
