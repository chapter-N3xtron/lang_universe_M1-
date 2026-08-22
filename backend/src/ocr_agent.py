"""Docling layout parsing and Ollama-backed OCR specialist."""
from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path
from uuid import uuid4

import requests

from src.document_attachments import OCR_UPLOAD_DIR
from src.workspace_policy import canonical_workspace

DEFAULT_SURYA_MODEL = "hf.co/datalab-to/surya-ocr-2-gguf:latest"
DEFAULT_GLM_MODEL = "glm-ocr:bf16"
MAX_OCR_BYTES = 25 * 1024 * 1024


def approved_document_path(document_ref: str, workspace: str | None) -> Path:
    """Resolve only a selected workspace file or an approved upload reference."""
    if document_ref.startswith("upload:"):
        name = document_ref.removeprefix("upload:")
        if not name or Path(name).name != name:
            raise ValueError("Invalid OCR upload reference")
        path = (OCR_UPLOAD_DIR / name).resolve()
        root = OCR_UPLOAD_DIR
    else:
        if not workspace:
            raise ValueError("An OCR document path requires a selected workspace")
        root = canonical_workspace(workspace)
        candidate = Path(document_ref).expanduser()
        path = (candidate if candidate.is_absolute() else root / candidate).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError("OCR document is outside the approved directory") from exc
    if not path.is_file():
        raise ValueError("OCR document was not found")
    if path.stat().st_size > MAX_OCR_BYTES:
        raise ValueError("OCR document exceeds the 25 MB limit")
    return path


def _docling_layout(path: Path, render_dir: Path) -> tuple[str, list[Path]]:
    try:
        from docling.document_converter import DocumentConverter
    except ImportError as exc:
        raise RuntimeError("Docling is required in the runtime image for OCR") from exc
    result = DocumentConverter().convert(str(path))
    document = result.document
    markdown = document.export_to_markdown()
    pages: list[Path] = []
    render_dir.mkdir(parents=True, exist_ok=True)
    for number, page in enumerate(getattr(document, "pages", {}).values(), 1):
        image = page.get_image(scale=2) if hasattr(page, "get_image") else None
        if image is None and getattr(page, "image", None) is not None:
            image = getattr(page.image, "pil_image", page.image)
        if image is not None:
            target = render_dir / f"page-{number}.png"
            image.save(target)
            pages.append(target)
    return markdown, pages


def _ollama_ocr(image: Path, model: str, base_url: str, timeout: int) -> str:
    encoded = base64.b64encode(image.read_bytes()).decode("ascii")
    response = requests.post(
        f"{base_url.rstrip('/')}/api/chat",
        json={
            "model": model,
            "messages": [{"role": "user", "content": "Transcribe this page faithfully.", "images": [encoded]}],
            "stream": False,
            "keep_alive": 0,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json().get("message", {}).get("content", "")


def run_ocr(task: str, document_ref: str, workspace: str | None, output_format: str = "markdown") -> dict:
    if output_format not in {"markdown", "json", "structured"}:
        raise ValueError("output_format must be markdown, json, or structured")
    path = approved_document_path(document_ref, workspace)
    run_dir = Path(os.getenv("OCR_ARTIFACT_DIR", str(path.parent / ".ocr-artifacts"))).resolve() / uuid4().hex
    layout, pages = _docling_layout(path, run_dir / "pages")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    timeout = int(os.getenv("OCR_OLLAMA_TIMEOUT", "300"))
    # Keep the model phases explicit and sequential: Surya must finish before
    # GLM-OCR starts, and keep_alive=0 unloads each request's model afterward.
    surya: list[str] = []
    for page in pages:
        surya.append(_ollama_ocr(page, os.getenv("OCR_SURYA_MODEL", DEFAULT_SURYA_MODEL), base_url, timeout))

    glm: list[str] = []
    for page in pages:
        glm.append(_ollama_ocr(page, os.getenv("OCR_GLM_MODEL", DEFAULT_GLM_MODEL), base_url, timeout))
    normalized = re.sub(r"\s+", " ", "\n".join(surya)).strip() or layout.strip()
    disagreements = [
        {"page": index, "surya": left, "glm": right}
        for index, (left, right) in enumerate(zip(surya, glm), 1)
        if re.sub(r"\s+", " ", left).strip() != re.sub(r"\s+", " ", right).strip()
    ]
    result = {"task": task, "document": str(path), "normalized": normalized, "layout_markdown": layout,
              "surya": surya, "glm_ocr": glm, "disagreements": disagreements}
    artifact = run_dir / ("result.json" if output_format in {"json", "structured"} else "result.md")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(result, indent=2) if artifact.suffix == ".json" else normalized, encoding="utf-8")
    manifest = run_dir / "manifest.json"
    manifest.write_text(json.dumps({"artifact": str(artifact), "pages": [str(p) for p in pages], "models": {"surya": os.getenv("OCR_SURYA_MODEL", DEFAULT_SURYA_MODEL), "glm_ocr": os.getenv("OCR_GLM_MODEL", DEFAULT_GLM_MODEL)}}, indent=2), encoding="utf-8")
    result.update({"artifact_path": str(artifact), "manifest_path": str(manifest)})
    return result


def specialist_message(result: dict, output_format: str) -> str:
    if output_format in {"json", "structured"}:
        return json.dumps(result, ensure_ascii=False)
    return (f"OCR complete. Manifest: {result['manifest_path']}\n"
            f"Artifact: {result['artifact_path']}\nNormalized result:\n{result['normalized']}\n"
            f"Surya and GLM-OCR outputs are preserved in the artifact; disagreements: {len(result['disagreements'])}.")
