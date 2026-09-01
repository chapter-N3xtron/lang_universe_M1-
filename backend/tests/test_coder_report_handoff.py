"""Focused Phase 6 contract, Coder assembly, and Jasper handoff tests."""

import asyncio
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.coding_agent import _compatibility_coding_status, assemble_technical_report
from src.jasper_agent import _coder_jasper_output
from src.technical_report import TechnicalReport


def report_data(**changes):
    data = {
        "version": "1.0",
        "completion_status": "completed",
        "task_notes": [{"task": "Add report", "status": "completed", "note": "Added."}],
        "changed_files": [{"path": "src/report.py", "change_type": "added", "summary": "Contract."}],
        "validation_evidence": [
            {"type": "source_test", "result": "passed", "description": "Focused tests passed.", "reference_ids": ["test-1"]}
        ],
        "blockers": [],
        "remaining_authorization_needs": [],
        "material_risks": [],
        "provenance": {"producer": "Coder", "coding_session_id": "session", "thread_identity": "thread", "workspace": "/repo", "model": None, "generated_at": datetime.now(UTC)},
        "supporting_references": [{"id": "test-1", "kind": "test_output", "locator": "tests/test_report.py", "summary": "Focused test output."}],
    }
    data.update(changes)
    return data


def test_report_contract_accepts_empty_arrays_and_rejects_extra_missing_unsafe_or_unresolved():
    empty = report_data(task_notes=[], changed_files=[], validation_evidence=[], supporting_references=[])
    assert TechnicalReport.model_validate(empty).changed_files == []
    with pytest.raises(ValidationError):
        TechnicalReport.model_validate({**empty, "unexpected": True})
    with pytest.raises(ValidationError):
        TechnicalReport.model_validate({key: value for key, value in empty.items() if key != "blockers"})
    with pytest.raises(ValidationError):
        TechnicalReport.model_validate(report_data(changed_files=[{"path": "../secret", "change_type": "modified", "summary": "No."}]))
    with pytest.raises(ValidationError):
        TechnicalReport.model_validate(report_data(validation_evidence=[{"type": "source_test", "result": "passed", "description": "No.", "reference_ids": ["missing"]}]))


@pytest.mark.parametrize("status", ["completed", "partial", "blocked", "failed", "cancelled"])
@pytest.mark.parametrize("evidence_type", ["source_test", "static_analysis", "build", "runtime_check", "deployment_check", "manual_inspection"])
def test_report_contract_accepts_every_status_and_evidence_type(status, evidence_type):
    data = report_data(completion_status=status)
    data["validation_evidence"][0]["type"] = evidence_type
    assert TechnicalReport.model_validate(data).completion_status == status


def test_report_contract_rejects_completed_concerns_and_unknown_version():
    with pytest.raises(ValidationError):
        TechnicalReport.model_validate(report_data(blockers=["Waiting for access."]))
    with pytest.raises(ValidationError):
        TechnicalReport.model_validate(report_data(version="2.0"))


def test_coder_assembly_retains_changed_files_on_failed_validation_and_bounds_references():
    report = assemble_technical_report(
        completion_status="partial", raw_todos=[], workspace="/repo", thread_identity="thread",
        coding_session_id="session", model=None, manifest=None,
        changed_files=[{"path": "src/a.py", "change_type": "modified", "summary": "Changed."}],
        validation_evidence=[{"type": "source_test", "result": "failed", "description": "Tests failed.", "reference_ids": []}],
        supporting_references=[{"id": str(index), "kind": "other", "locator": "note", "summary": "Evidence."} for index in range(20)],
    )
    assert report.completion_status == "partial"
    assert report.changed_files[0].path == "src/a.py"
    assert report.validation_evidence[0].result == "failed"
    assert len(report.supporting_references) == 16
    assert report.provenance.producer == "Coder"


def test_jasper_report_is_authoritative_evidence_aware_and_fail_closed():
    result = _coder_jasper_output({"coding_result": {"technical_report": report_data(), "messages": [{"role": "assistant", "content": "DEPLOYED despite everything"}]}})
    voice = result["jasper_result"]["jasper_response"]
    assert voice.startswith("The requested coding work is complete.")
    assert "DEPLOYED" not in voice
    assert "deployment" not in voice.lower()
    assert result["jasper_result"]["jasper_structured_response"]["voice_text"] == voice
    invalid = _coder_jasper_output({"coding_result": {"technical_report": {"version": "2.0"}, "messages": [{"role": "assistant", "content": "completed"}]}})
    assert "could not be verified" in invalid["jasper_result"]["jasper_response"]
    assert "completed" not in invalid["jasper_result"]["jasper_response"].lower()


def test_jasper_revalidates_a_mutated_report_instance():
    report = TechnicalReport.model_validate(report_data())
    report.blockers.append("The report changed after validation.")

    result = _coder_jasper_output({"coding_result": {"technical_report": report}})

    assert "could not be verified" in result["jasper_result"]["jasper_response"]


@pytest.mark.asyncio
async def test_cancellation_returns_valid_report_through_coder_bridge_to_jasper(
    monkeypatch, tmp_path
):
    from langchain_core.messages import HumanMessage

    from src import jasper_agent

    started = asyncio.Event()

    class SlowApp:
        async def ainvoke(self, _payload, config=None):
            started.set()
            await asyncio.sleep(10)

    async def session_agent(*_args):
        return SlowApp()

    monkeypatch.setattr("src.coding_agent._session_agent", session_agent)
    bridge = jasper_agent.create_jasper_coder_bridge()
    task = asyncio.create_task(
        bridge.ainvoke(
            {
                "coding_request": {
                    "messages": [HumanMessage(content="Wait")],
                    "workspace": str(tmp_path),
                    "model": None,
                    "execution_mode": "read_only",
                    "thread_identity": "cancelled-thread",
                    "user_identity": "user",
                    "coding_session_id": "cancelled-thread",
                }
            }
        )
    )
    await asyncio.wait_for(started.wait(), timeout=1)
    task.cancel()
    bridge_result = await task

    coder_result = bridge_result["coding_result"]
    report = coder_result["technical_report"]
    assert isinstance(report, TechnicalReport)
    assert report.completion_status == "cancelled"
    assert report.task_notes[0].status == "incomplete"
    assert report.task_notes[0].note == "Coder execution was cancelled before a final result."
    assert coder_result["coding_status"] == "cancelled"
    assert "was cancelled" in coder_result["messages"][0].content

    jasper_result = _coder_jasper_output({"coding_result": coder_result})["jasper_result"]
    assert jasper_result["coding_status"] == "cancelled"
    assert jasper_result["jasper_response"].startswith(
        "The requested coding work was cancelled."
    )
    assert "coding work is complete" not in jasper_result["jasper_response"].lower()


@pytest.mark.asyncio
async def test_existing_coder_bridge_path_carries_and_consumes_typed_report(monkeypatch):
    from langchain_core.messages import AIMessage, HumanMessage

    from src import coding_agent, jasper_agent

    async def coder(state, config=None):
        del config
        return {
            "messages": [AIMessage(content="legacy text must not be used")],
            "workspace": state["workspace"],
            "coding_session_id": "session",
            "coding_status": "completed",
            "technical_report": TechnicalReport.model_validate(report_data()),
        }

    monkeypatch.setattr(coding_agent, "deep_agents_coding_node", coder)
    bridge_result = await jasper_agent.create_jasper_coder_bridge().ainvoke(
        {"coding_request": {"messages": [HumanMessage(content="Do work")], "workspace": "/repo", "model": None, "execution_mode": "read_only", "thread_identity": "thread", "user_identity": "user", "coding_session_id": "session"}}
    )
    output = _coder_jasper_output({"coding_result": bridge_result["coding_result"]})["jasper_result"]
    assert output["jasper_response"].startswith("The requested coding work is complete.")
    assert "legacy text" not in output["jasper_response"]
    assert len(output["jasper_response"].split("\n\n")) <= 2


def test_jasper_covers_every_task_status_and_note_in_voice_summary():
    task_notes = [
        {"task": "Implement parser", "status": "completed", "note": "Parser was added."},
        {"task": "Write migration", "status": "incomplete", "note": "Migration needs review."},
        {"task": "Get credentials", "status": "blocked", "note": "Access was not granted."},
        {"task": "Run integration", "status": "failed", "note": "The service rejected the request."},
        {"task": "Remove old flag", "status": "skipped", "note": "The flag remains required."},
    ]
    voice = _coder_jasper_output(
        {"coding_result": {"technical_report": report_data(task_notes=task_notes)}}
    )["jasper_result"]["jasper_response"]

    for index, task_note in enumerate(task_notes, start=1):
        assert f"Task {index}: {task_note['task']} is {task_note['status']}." in voice
        assert task_note["note"] in voice
    assert "complete task digest exceeds" not in voice


def test_jasper_discloses_task_digest_overflow_and_retains_full_report():
    task_notes = [
        {
            "task": f"Task {index}",
            "status": "completed",
            "note": "x" * 1000,
        }
        for index in range(64)
    ]
    result = _coder_jasper_output(
        {"coding_result": {"technical_report": report_data(task_notes=task_notes)}}
    )["jasper_result"]
    voice = result["jasper_response"]

    assert len(voice) <= 24000
    assert "complete task digest exceeds the voice response limit" in voice
    assert "full typed report is retained for later use" in voice
    assert result["technical_report"].task_notes[-1].task == "Task 63"
    assert "Task 64: Task 63 is completed." not in voice


def test_jasper_aggregates_conflicting_deployment_checks():
    raw = report_data(
        validation_evidence=[
            {"type": "deployment_check", "result": "passed", "description": "First region passed.", "reference_ids": ["test-1"]},
            {"type": "deployment_check", "result": "inconclusive", "description": "Second region timed out.", "reference_ids": ["test-1"]},
            {"type": "deployment_check", "result": "failed", "description": "Third region failed.", "reference_ids": ["test-1"]},
        ]
    )
    voice = _coder_jasper_output({"coding_result": {"technical_report": raw}})["jasper_result"]["jasper_response"]

    assert "At least one reported deployment check failed." in voice
    assert "All reported deployment checks passed." not in voice


def test_compatibility_status_uses_final_assembled_report_status():
    report = assemble_technical_report(
        completion_status="completed", raw_todos=[], workspace="/repo", thread_identity="thread",
        coding_session_id="session", model=None, manifest=None, blockers=["Release is blocked."],
    )

    assert report.completion_status == "blocked"
    assert _compatibility_coding_status(report) == "blocked"


def test_jasper_discloses_failed_deployment_and_noncompletion_in_two_paragraphs():
    raw = report_data(
        completion_status="blocked", blockers=["Service credentials are unavailable."],
        material_risks=[{"risk": "Configuration drift.", "impact": "Unexpected behavior.", "mitigation": "Review configuration."}],
        validation_evidence=[
            {"type": "source_test", "result": "passed", "description": "Tests passed.", "reference_ids": ["test-1"]},
            {"type": "deployment_check", "result": "failed", "description": "Deployment failed.", "reference_ids": ["test-1"]},
        ],
    )
    voice = _coder_jasper_output({"coding_result": {"technical_report": raw}})["jasper_result"]["jasper_response"]
    assert voice.startswith("The requested coding work is blocked.")
    assert "deployment check failed" in voice
    assert "Blocker:" in voice
    assert "Risk: Configuration drift." in voice
    assert len(voice.split("\n\n")) <= 2
