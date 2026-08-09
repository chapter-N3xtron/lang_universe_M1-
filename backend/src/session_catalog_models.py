"""Typed public contracts for the owner-scoped visual session library."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


SessionStatus = Literal["open", "closed", "forked"]
FilterCombinator = Literal["and", "or"]


class FilterRule(StrictModel):
    kind: Literal["rule"] = "rule"
    field: Literal[
        "created_at",
        "last_activity_at",
        "workspace",
        "agent",
        "status",
        "has_visuals",
        "active_minutes",
        "text",
    ]
    operator: Literal[
        "equals",
        "notEquals",
        "contains",
        "doesNotContain",
        "beginsWith",
        "endsWith",
        "greaterThan",
        "greaterThanOrEqual",
        "lessThan",
        "lessThanOrEqual",
        "between",
        "in",
        "notIn",
        "isNull",
        "isNotNull",
    ]
    value: str | int | float | bool | list[str | int | float] | None = None


class FilterGroup(StrictModel):
    kind: Literal["group"] = "group"
    combinator: FilterCombinator = "and"
    rules: list[FilterRule | FilterGroup] = Field(default_factory=list, max_length=30)
    not_: bool = Field(default=False, alias="not")


FilterGroup.model_rebuild()


class SortRule(StrictModel):
    field: Literal[
        "created_at",
        "last_activity_at",
        "short_description",
        "active_minutes",
        "status",
        "visual_count",
    ]
    direction: Literal["asc", "desc"]


class SessionQuery(StrictModel):
    owner_id: str = Field(min_length=1, max_length=128)
    filters: FilterGroup = Field(default_factory=FilterGroup)
    sort: list[SortRule] = Field(
        default_factory=lambda: [SortRule(field="last_activity_at", direction="desc")],
        max_length=4,
    )
    cursor: str | None = Field(default=None, max_length=512)
    page_size: int = Field(default=25, ge=1, le=100)
    search: str = Field(default="", max_length=500)
    visible_columns: list[str] = Field(default_factory=list, max_length=20)


class WorkspaceSummary(StrictModel):
    workspace_id: str
    name: str
    repository_binding_state: Literal["bound", "unbound", "unavailable"]


class AgentSummary(StrictModel):
    profile_id: str
    profile_version: str = "1"
    role: str = "participant"


class SessionCatalogRow(StrictModel):
    session_id: str
    thread_id: str
    parent_session_id: str | None = None
    parent_thread_id: str | None = None
    created_at: datetime
    last_activity_at: datetime
    short_description: str
    long_description: str
    active_minutes: int = 0
    active_time_observed: bool = True
    status: SessionStatus
    workspaces: list[WorkspaceSummary] = Field(default_factory=list)
    agents: list[AgentSummary] = Field(default_factory=list)
    visual_count: int = 0
    has_visuals: bool = False
    summary_version: int = 1


class SessionQueryResponse(StrictModel):
    rows: list[SessionCatalogRow]
    next_cursor: str | None = None
    total: int


class SavedViewInput(StrictModel):
    owner_id: str = Field(min_length=1, max_length=128)
    view_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=120)
    query: SessionQuery


class SessionCloseInput(StrictModel):
    owner_id: str = Field(min_length=1, max_length=128)
    summary: str | None = Field(default=None, max_length=2000)
    tent_poles: list[str] = Field(default_factory=list, max_length=20)


class SessionOpenInput(StrictModel):
    owner_id: str = Field(min_length=1, max_length=128)


class ModelPreferenceInput(StrictModel):
    owner_id: str = Field(min_length=1, max_length=128)
    model_id: str = Field(min_length=1, max_length=256)


class SessionForkInput(StrictModel):
    owner_id: str = Field(min_length=1, max_length=128)
    checkpoint_id: str | None = Field(default=None, max_length=128)


class SessionArtifactTitleInput(StrictModel):
    owner_id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=160)
