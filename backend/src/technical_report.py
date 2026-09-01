"""Strict Coder-to-Jasper technical report contract, version 1.0."""

from __future__ import annotations

from datetime import datetime
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictReportModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, revalidate_instances="always"
    )


ShortText = Field(min_length=1, max_length=1000)
LocatorText = Field(min_length=1, max_length=1024)


class TaskNote(StrictReportModel):
    task: str = ShortText
    status: Literal["completed", "incomplete", "blocked", "failed", "skipped"]
    note: str = ShortText


class ChangedFile(StrictReportModel):
    path: str = LocatorText
    change_type: Literal["added", "modified", "deleted", "renamed"]
    summary: str = ShortText


class ValidationEvidence(StrictReportModel):
    type: Literal[
        "source_test",
        "static_analysis",
        "build",
        "runtime_check",
        "deployment_check",
        "manual_inspection",
    ]
    result: Literal["passed", "failed", "not_run", "inconclusive"]
    description: str = ShortText
    reference_ids: list[str] = Field(default_factory=list, max_length=8)


class AuthorizationNeed(StrictReportModel):
    action: str = ShortText
    reason: str = ShortText


class MaterialRisk(StrictReportModel):
    risk: str = ShortText
    impact: str = ShortText
    mitigation: str = ShortText


class ReportProvenance(StrictReportModel):
    producer: Literal["Coder"]
    coding_session_id: str = Field(min_length=1, max_length=256)
    thread_identity: str = Field(min_length=1, max_length=256)
    workspace: str = LocatorText
    model: str | None = Field(default=None, max_length=256)
    generated_at: datetime

    @field_validator("generated_at", mode="before")
    @classmethod
    def parse_iso_timestamp(cls, value):
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("generated_at must be ISO-8601") from exc
        if not isinstance(value, datetime):
            raise ValueError("generated_at must be ISO-8601")
        return value


class SupportingReference(StrictReportModel):
    id: str = Field(min_length=1, max_length=128)
    kind: Literal["file", "command_output", "test_output", "execution_manifest", "other"]
    locator: str = LocatorText
    summary: str = ShortText


class TechnicalReport(StrictReportModel):
    """The sole authoritative Coder result passed to Jasper."""

    version: Literal["1.0"]
    completion_status: Literal["completed", "partial", "blocked", "failed", "cancelled"]
    task_notes: list[TaskNote] = Field(max_length=64)
    changed_files: list[ChangedFile] = Field(max_length=256)
    validation_evidence: list[ValidationEvidence] = Field(max_length=64)
    blockers: list[str] = Field(max_length=32)
    remaining_authorization_needs: list[AuthorizationNeed] = Field(max_length=32)
    material_risks: list[MaterialRisk] = Field(max_length=32)
    provenance: ReportProvenance
    supporting_references: list[SupportingReference] = Field(max_length=16)

    @model_validator(mode="after")
    def validate_consistency(self) -> TechnicalReport:
        for blocker in self.blockers:
            if not blocker.strip():
                raise ValueError("blockers must contain non-empty text")
        for changed_file in self.changed_files:
            path = PurePosixPath(changed_file.path)
            if (
                path.is_absolute()
                or ".." in path.parts
                or changed_file.path.startswith("~")
                or not changed_file.path.strip()
            ):
                raise ValueError("changed file paths must be repository-relative")
        reference_ids = [reference.id for reference in self.supporting_references]
        if len(reference_ids) != len(set(reference_ids)):
            raise ValueError("supporting reference IDs must be unique")
        known_reference_ids = set(reference_ids)
        for evidence in self.validation_evidence:
            unresolved = set(evidence.reference_ids) - known_reference_ids
            if unresolved:
                raise ValueError("validation evidence references must resolve")
        if self.completion_status == "completed" and (
            self.blockers or self.remaining_authorization_needs
        ):
            raise ValueError(
                "completed reports cannot contain blockers or authorization needs"
            )
        return self
