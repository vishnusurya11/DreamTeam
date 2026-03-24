from __future__ import annotations
from datetime import datetime, timezone
from enum import StrEnum
from typing import Optional
from uuid import uuid4
from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PipelineStage(StrEnum):
    INBOX = "INBOX"
    PLANNING = "PLANNING"
    BACKLOG = "BACKLOG"
    BUILDING = "BUILDING"
    QA = "QA"
    REVIEW = "REVIEW"
    SHIP = "SHIP"


class AgentRole(StrEnum):
    PLANNER = "planner"
    BUILDER = "builder"
    QA = "qa"
    REVIEWER = "reviewer"


class AgentLocation(StrEnum):
    PLANNING_ROOM = "planning_room"
    DEV_AREA = "dev_area"
    QA_LAB = "qa_lab"
    REVIEW_ROOM = "review_room"
    MEETING_ROOM = "meeting_room"
    CAFETERIA = "cafeteria"


class TaskPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class QAVerdictType(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


class ReviewVerdictType(StrEnum):
    APPROVE = "APPROVE"
    REQUEST_CHANGES = "REQUEST_CHANGES"


class QAVerdict(BaseModel):
    verdict: QAVerdictType
    reason: str = ""


class ReviewVerdict(BaseModel):
    verdict: ReviewVerdictType
    reason: str = ""


class LogEntry(BaseModel):
    timestamp: str = Field(default_factory=_now)
    agent_name: str
    stage: PipelineStage
    message: str


class Project(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    name: str
    description: str = ""
    repo_url: Optional[str] = None
    priority: TaskPriority = TaskPriority.MEDIUM
    is_active: bool = True
    created_at: str = Field(default_factory=_now)


class Task(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    project_id: str
    title: str
    description: str
    stage: PipelineStage = PipelineStage.INBOX
    priority: TaskPriority = TaskPriority.MEDIUM
    assigned_agent: Optional[str] = None
    history: list[LogEntry] = Field(default_factory=list)
    code_output: Optional[str] = None
    qa_report: Optional[str] = None
    review_notes: Optional[str] = None
    planning_notes: Optional[str] = None
    subtask_ids: list[str] = Field(default_factory=list)
    parent_task_id: Optional[str] = None
    retries: int = 0
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class AgentConfig(BaseModel):
    name: str
    role: AgentRole
    personality: str
    is_busy: bool = False
    current_task_id: Optional[str] = None
    location: AgentLocation = AgentLocation.CAFETERIA


class PlanningFailure(BaseModel):
    fail_count: int = 0
    last_failure_at: str = Field(default_factory=_now)


class PipelineState(BaseModel):
    projects: dict[str, Project] = Field(default_factory=dict)
    tasks: dict[str, Task] = Field(default_factory=dict)
    agents: dict[str, AgentConfig] = Field(default_factory=dict)
    planning_failures: dict[str, PlanningFailure] = Field(default_factory=dict)
