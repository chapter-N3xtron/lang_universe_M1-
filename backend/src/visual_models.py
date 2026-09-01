"""Canonical structured response models for Jasper and visual surfaces."""

from __future__ import annotations

import json
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = 2
MAX_ARTIFACT_BYTES = 256 * 1024
MAX_VOICE_TEXT_CHARACTERS = 24_000
SAFE_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class EvidenceSource(StrictModel):
    id: str = Field(min_length=1, max_length=64, pattern=SAFE_ID_PATTERN)
    kind: Literal["repo_file", "web_url", "user_input"]
    locator: str = Field(min_length=1, max_length=2048)
    title: str = Field(min_length=1, max_length=240)
    content_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_locator(self) -> EvidenceSource:
        if self.kind == "web_url" and not self.locator.startswith(
            ("https://", "http://")
        ):
            raise ValueError("Web evidence locators must use HTTP or HTTPS")
        if self.kind == "repo_file":
            path = self.locator.replace("\\", "/")
            if path.startswith("/") or ".." in path.split("/"):
                raise ValueError("Repository evidence locators must be relative paths")
        return self


class ConceptMapNode(StrictModel):
    id: str = Field(min_length=1, max_length=64, pattern=SAFE_ID_PATTERN)
    label: str = Field(min_length=1, max_length=120)
    detail: str | None = Field(default=None, max_length=2000)
    narration: str = Field(min_length=1, max_length=2000)
    kind: Literal["concept", "group", "code", "decision", "input", "output"] = "concept"
    claim_status: Literal[
        "observed", "researched", "user_defined", "proposed", "inferred"
    ]
    evidence_refs: list[str] = Field(min_length=1, max_length=8)


class ConceptMapEdge(StrictModel):
    source: str = Field(min_length=1, max_length=64, pattern=SAFE_ID_PATTERN)
    target: str = Field(min_length=1, max_length=64, pattern=SAFE_ID_PATTERN)
    label: str | None = Field(default=None, max_length=120)
    relation: Literal["relates_to", "contains", "calls", "depends_on", "flows_to"] = (
        "relates_to"
    )
    claim_status: Literal[
        "observed", "researched", "user_defined", "proposed", "inferred"
    ]
    evidence_refs: list[str] = Field(min_length=1, max_length=8)


class ConceptMapPayload(StrictModel):
    grounding_kind: Literal["repo", "web", "user_input", "mixed"]
    sources: list[EvidenceSource] = Field(min_length=1, max_length=32)
    nodes: list[ConceptMapNode] = Field(min_length=1, max_length=100)
    edges: list[ConceptMapEdge] = Field(default_factory=list, max_length=200)
    narration_order: list[str] = Field(min_length=1, max_length=100)
    direction: Literal["top_to_bottom", "left_to_right"] = "left_to_right"

    @model_validator(mode="after")
    def validate_graph(self) -> ConceptMapPayload:
        source_ids = [source.id for source in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("Concept-map evidence source IDs must be unique")
        known_sources = set(source_ids)
        source_kinds = {source.id: source.kind for source in self.sources}
        required_source_kind = {
            "repo": "repo_file",
            "web": "web_url",
            "user_input": "user_input",
        }.get(self.grounding_kind)
        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("Concept-map node IDs must be unique")
        known = set(node_ids)
        if len(self.narration_order) != len(set(self.narration_order)):
            raise ValueError("Concept-map narration order must not repeat nodes")
        if set(self.narration_order) != known:
            raise ValueError(
                "Concept-map narration order must contain every node exactly once"
            )
        for node in self.nodes:
            unknown = set(node.evidence_refs) - known_sources
            if unknown:
                raise ValueError(
                    "Every concept-map node evidence reference must identify a "
                    f"source; unknown references: {', '.join(sorted(unknown))}"
                )
            if required_source_kind and not any(
                source_kinds[ref] == required_source_kind for ref in node.evidence_refs
            ):
                raise ValueError(
                    f"Every {self.grounding_kind}-grounded node must cite at least "
                    f"one {required_source_kind} source"
                )
            self._validate_claim_status(
                node.claim_status, node.evidence_refs, source_kinds
            )
        for edge in self.edges:
            if edge.source not in known or edge.target not in known:
                raise ValueError(
                    "Every concept-map edge endpoint must reference a node"
                )
            unknown = set(edge.evidence_refs) - known_sources
            if unknown:
                raise ValueError(
                    "Every concept-map edge evidence reference must identify a "
                    f"source; unknown references: {', '.join(sorted(unknown))}"
                )
            if required_source_kind and not any(
                source_kinds[ref] == required_source_kind for ref in edge.evidence_refs
            ):
                raise ValueError(
                    f"Every {self.grounding_kind}-grounded edge must cite at least "
                    f"one {required_source_kind} source"
                )
            self._validate_claim_status(
                edge.claim_status, edge.evidence_refs, source_kinds
            )
        if len(known) > 1:
            adjacency = {node_id: set() for node_id in known}
            for edge in self.edges:
                adjacency[edge.source].add(edge.target)
                adjacency[edge.target].add(edge.source)
            visited: set[str] = set()
            pending = [node_ids[0]]
            while pending:
                current = pending.pop()
                if current in visited:
                    continue
                visited.add(current)
                pending.extend(adjacency[current] - visited)
            disconnected = sorted(known - visited)
            if disconnected:
                raise ValueError(
                    "Concept map must be a single connected graph; disconnected "
                    f"node IDs: {', '.join(disconnected)}. Add edges connecting "
                    "every node to the main flow."
                )
        return self

    @staticmethod
    def _validate_claim_status(
        status: str, refs: list[str], source_kinds: dict[str, str]
    ) -> None:
        required_kind = {
            "observed": "repo_file",
            "researched": "web_url",
            "user_defined": "user_input",
            "proposed": "user_input",
        }.get(status)
        if required_kind and not any(
            source_kinds[ref] == required_kind for ref in refs
        ):
            raise ValueError(
                f"A {status} concept-map claim must cite at least one "
                f"{required_kind} source"
            )


class ConceptMapArtifact(StrictModel):
    renderer: Literal["react_flow"] = "react_flow"
    artifact_id: str = Field(
        default_factory=lambda: f"visual-{uuid4().hex}",
        min_length=1,
        max_length=64,
        pattern=SAFE_ID_PATTERN,
    )
    title: str = Field(min_length=1, max_length=160)
    alt_text: str = Field(min_length=1, max_length=4000)
    source_message_id: str | None = Field(default=None, max_length=128)
    payload: ConceptMapPayload

    @model_validator(mode="after")
    def validate_serialized_size(self) -> ConceptMapArtifact:
        encoded = json.dumps(
            self.model_dump(mode="json"), separators=(",", ":")
        ).encode("utf-8")
        if len(encoded) > MAX_ARTIFACT_BYTES:
            raise ValueError("Visual artifact exceeds the 256 KiB limit")
        return self


class DrawConceptMapInput(StrictModel):
    """Arguments accepted by Jasper's validated concept-map tool."""

    title: str = Field(min_length=1, max_length=160)
    alt_text: str = Field(min_length=1, max_length=4000)
    grounding_kind: Literal["repo", "web", "user_input", "mixed"]
    nodes: list[ConceptMapNode] = Field(min_length=1, max_length=100)
    edges: list[ConceptMapEdge] = Field(default_factory=list, max_length=200)
    narration_order: list[str] = Field(min_length=1, max_length=100)
    direction: Literal["top_to_bottom", "left_to_right"] = "left_to_right"


VisualArtifact = Annotated[ConceptMapArtifact, Field(discriminator="renderer")]


class LayoutSuggestion(StrictModel):
    mode: Literal["chat", "visual", "split", "compact_chat"]
    reason: str = Field(min_length=1, max_length=240)


class ResponseDiagnostic(StrictModel):
    code: Literal[
        "structured_output_unavailable",
        "structured_output_invalid",
        "provider_unavailable",
    ]
    message: str = Field(min_length=1, max_length=240)
    recoverable: bool = True


class JasperResponse(StrictModel):
    version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    voice_text: str = Field(min_length=1, max_length=MAX_VOICE_TEXT_CHARACTERS)
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence_basis: str | None = Field(default=None, min_length=1, max_length=240)
    artifacts: list[VisualArtifact] = Field(default_factory=list, max_length=4)
    layout_suggestion: LayoutSuggestion | None = None
    diagnostic: ResponseDiagnostic | None = None


def _portable_schema(value):
    """Remove OpenAPI-only hints while preserving JSON Schema validation."""

    if isinstance(value, dict):
        return {
            key: _portable_schema(item)
            for key, item in value.items()
            if key != "discriminator"
        }
    if isinstance(value, list):
        return [_portable_schema(item) for item in value]
    return value


def jasper_response_json_schema() -> dict:
    """Return the portable browser contract generated from the Pydantic model."""

    schema = _portable_schema(JasperResponse.model_json_schema())
    schema["$id"] = "https://agent-chat.local/schemas/jasper-response-v1.json"
    return schema


_OPENAI_UNSUPPORTED_SCHEMA_KEYS = frozenset(
    {
        "$id",
        "$schema",
        "default",
        "exclusiveMaximum",
        "exclusiveMinimum",
        "examples",
        "format",
        "maxItems",
        "maxLength",
        "maximum",
        "minItems",
        "minLength",
        "minimum",
        "multipleOf",
        "pattern",
        "title",
        "uniqueItems",
    }
)


def _openai_schema(value):
    if isinstance(value, list):
        return [_openai_schema(item) for item in value]
    if not isinstance(value, dict):
        return value

    one_of = value.get("oneOf")
    if isinstance(one_of, list):
        if len(one_of) == 1:
            value = {
                key: item
                for key, item in value.items()
                if key not in {"discriminator", "oneOf"}
            }
            value.update(one_of[0])
        else:
            value = {
                key: item
                for key, item in value.items()
                if key not in {"discriminator", "oneOf"}
            }
            value["anyOf"] = one_of

    result = {}
    for key, item in value.items():
        if key in _OPENAI_UNSUPPORTED_SCHEMA_KEYS or key == "discriminator":
            continue
        if key == "const":
            result["enum"] = [item]
        else:
            result[key] = _openai_schema(item)

    if result.get("type") == "object":
        properties = result.get("properties", {})
        result["properties"] = properties
        result["required"] = list(properties)
        result["additionalProperties"] = False

    return result


def openai_jasper_response_json_schema() -> dict:
    """Return Jasper's strict Structured Outputs schema for OpenAI models."""

    schema = _openai_schema(JasperResponse.model_json_schema())
    schema["title"] = "JasperResponse"
    return schema


def safe_text_response(
    text: str,
    *,
    code: Literal[
        "structured_output_unavailable",
        "structured_output_invalid",
        "provider_unavailable",
    ],
    message: str,
) -> JasperResponse:
    """Return a validated, artifact-free response for the terminal fallback path."""

    safe_text = text.strip() or "I could not complete that response. Please try again."
    return JasperResponse(
        voice_text=safe_text[:MAX_VOICE_TEXT_CHARACTERS],
        diagnostic=ResponseDiagnostic(code=code, message=message),
    )
