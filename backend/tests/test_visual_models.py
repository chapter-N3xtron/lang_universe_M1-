import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.visual_models import (
    ConceptMapArtifact,
    ConceptMapEdge,
    ConceptMapNode,
    ConceptMapPayload,
    EvidenceSource,
    JasperResponse,
    jasper_response_json_schema,
    safe_text_response,
)

SOURCE = EvidenceSource(
    id="source-one",
    kind="user_input",
    locator="current-user-message",
    title="Current user request",
    content_sha256="a" * 64,
)


def _node(node_id: str, label: str, **kwargs) -> ConceptMapNode:
    return ConceptMapNode(
        id=node_id,
        label=label,
        narration=f"Explanation of {label}.",
        claim_status="user_defined",
        evidence_refs=[SOURCE.id],
        **kwargs,
    )


def _edge(source: str, target: str) -> ConceptMapEdge:
    return ConceptMapEdge(
        source=source,
        target=target,
        claim_status="user_defined",
        evidence_refs=[SOURCE.id],
    )


def _artifact() -> ConceptMapArtifact:
    return ConceptMapArtifact(
        artifact_id="neuron-map",
        title="How a neuron fires",
        alt_text="A signal flows from dendrites through the cell body to the axon.",
        payload=ConceptMapPayload(
            grounding_kind="user_input",
            sources=[SOURCE],
            nodes=[
                _node("dendrites", "Dendrites", kind="input"),
                _node("axon", "Axon", kind="output"),
            ],
            edges=[_edge("dendrites", "axon")],
            narration_order=["dendrites", "axon"],
        ),
    )


def test_jasper_response_round_trip():
    response = JasperResponse(
        voice_text="A neuron receives a signal and passes it along its axon.",
        confidence_score=0.82,
        confidence_basis="The explanation is grounded in the supplied evidence.",
        artifacts=[_artifact()],
    )
    restored = JasperResponse.model_validate_json(response.model_dump_json())
    assert restored == response
    assert restored.artifacts[0].renderer == "react_flow"
    assert restored.confidence_score == 0.82


def test_jasper_confidence_is_bounded_or_unknown():
    assert JasperResponse(voice_text="Unknown.").confidence_score is None
    with pytest.raises(ValidationError):
        JasperResponse(voice_text="Overconfident.", confidence_score=1.01)


def test_unknown_fields_are_rejected():
    payload = _artifact().model_dump()
    payload["javascript"] = "alert(1)"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ConceptMapArtifact.model_validate(payload)


def test_duplicate_nodes_and_missing_edge_endpoints_are_rejected():
    with pytest.raises(ValidationError, match="unique"):
        ConceptMapPayload(
            grounding_kind="user_input",
            sources=[SOURCE],
            nodes=[
                _node("same", "One"),
                _node("same", "Two"),
            ],
            narration_order=["same"],
        )

    with pytest.raises(ValidationError, match="endpoint"):
        ConceptMapPayload(
            grounding_kind="user_input",
            sources=[SOURCE],
            nodes=[_node("one", "One")],
            edges=[_edge("one", "missing")],
            narration_order=["one"],
        )


def test_disconnected_concept_map_is_rejected():
    with pytest.raises(ValidationError, match="single connected graph"):
        ConceptMapPayload(
            grounding_kind="user_input",
            sources=[SOURCE],
            nodes=[
                _node("langgraph", "LangGraph"),
                _node("jasper", "Jasper"),
                _node("tools", "Tools"),
                _node("output", "Output"),
            ],
            edges=[
                _edge("langgraph", "jasper"),
                _edge("tools", "output"),
            ],
            narration_order=["langgraph", "jasper", "tools", "output"],
        )


def test_graph_limits_are_enforced():
    with pytest.raises(ValidationError):
        ConceptMapPayload(
            grounding_kind="user_input",
            sources=[SOURCE],
            nodes=[_node(f"node-{index}", "Node") for index in range(101)],
            narration_order=[f"node-{index}" for index in range(101)],
        )


def test_grounding_kind_and_evidence_references_are_enforced():
    with pytest.raises(ValidationError, match="repo-grounded node"):
        ConceptMapPayload(
            grounding_kind="repo",
            sources=[SOURCE],
            nodes=[_node("claim", "Unsupported repo claim")],
            narration_order=["claim"],
        )

    with pytest.raises(ValidationError, match="unknown references"):
        ConceptMapPayload(
            grounding_kind="mixed",
            sources=[SOURCE],
            nodes=[
                ConceptMapNode(
                    id="claim",
                    label="Unknown source",
                    narration="An unknown-source claim.",
                    claim_status="inferred",
                    evidence_refs=["missing"],
                )
            ],
            narration_order=["claim"],
        )


def test_proposed_user_architecture_is_distinct_from_observed_code():
    payload = ConceptMapPayload(
        grounding_kind="user_input",
        sources=[SOURCE],
        nodes=[
            ConceptMapNode(
                id="future-service",
                label="Future service",
                narration="This service is part of the proposed design.",
                claim_status="proposed",
                evidence_refs=[SOURCE.id],
            )
        ],
        narration_order=["future-service"],
    )
    assert payload.nodes[0].claim_status == "proposed"

    with pytest.raises(ValidationError, match="observed.*repo_file"):
        ConceptMapPayload(
            grounding_kind="mixed",
            sources=[SOURCE],
            nodes=[
                ConceptMapNode(
                    id="false-observation",
                    label="Not implemented",
                    narration="This is not implemented.",
                    claim_status="observed",
                    evidence_refs=[SOURCE.id],
                )
            ],
            narration_order=["false-observation"],
        )


def test_safe_text_fallback_never_contains_artifacts():
    response = safe_text_response(
        "A useful plain response.",
        code="structured_output_invalid",
        message="The selected model could not produce a valid visual response.",
    )
    assert response.voice_text == "A useful plain response."
    assert response.artifacts == []
    assert response.diagnostic is not None


def test_schema_is_json_serializable_and_discriminated():
    schema = JasperResponse.model_json_schema()
    serialized = json.dumps(schema)
    assert "react_flow" in serialized
    assert "discriminator" in serialized


def test_committed_frontend_schema_is_current():
    schema_path = (
        Path(__file__).resolve().parents[2]
        / "agent-chat-ui"
        / "src"
        / "lib"
        / "visual"
        / "jasper-response.schema.json"
    )
    committed = json.loads(schema_path.read_text())
    expected = jasper_response_json_schema()
    assert committed == expected
