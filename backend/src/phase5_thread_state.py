"""Bounded checkpoint-state values for Phase 5 session document links."""

from __future__ import annotations

import re
from typing import Any

MAX_SESSION_DOCUMENT_IDS = 100
_STABLE_DOCUMENT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def normalize_session_document_ids(value: Any) -> list[str]:
    """Validate and normalize one authoritative complete document-ID list.

    The returned list contains only stable IDs, deduplicated in first-seen order.
    This function deliberately accepts no link envelopes or document metadata.
    """

    if type(value) is not list:
        raise ValueError("session_document_ids must be a list")

    normalized: list[str] = []
    seen: set[str] = set()
    for document_id in value:
        if type(document_id) is not str or not _STABLE_DOCUMENT_ID.fullmatch(
            document_id
        ):
            raise ValueError("session_document_ids contains an invalid document ID")
        if document_id in seen:
            continue
        seen.add(document_id)
        normalized.append(document_id)
        if len(normalized) > MAX_SESSION_DOCUMENT_IDS:
            raise ValueError("session_document_ids exceeds 100 unique document IDs")

    return normalized


def replace_session_document_ids(_current: list[str], replacement: Any) -> list[str]:
    """Replace the prior set with one validated authoritative complete list."""

    return normalize_session_document_ids(replacement)
