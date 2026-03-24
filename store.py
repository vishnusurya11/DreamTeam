from __future__ import annotations
import json
import os
import threading
import time
from datetime import datetime, timezone
from typing import Optional
from fastapi import WebSocket
from models import (
    AgentConfig, AgentLocation, AgentRole, LogEntry,
    PipelineStage, PipelineState, PlanningFailure, Project, Task, TaskPriority,
)
from config import STATE_FILE, AGENTS, WORKSPACES_DIR, DATA_DIR


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# Map pipeline stages to agent locations
STAGE_LOCATION_MAP = {
    PipelineStage.PLANNING: AgentLocation.MEETING_ROOM,
    PipelineStage.BUILDING: AgentLocation.DEV_AREA,
    PipelineStage.QA: AgentLocation.QA_LAB,
    PipelineStage.REVIEW: AgentLocation.REVIEW_ROOM,
}


class StateStore:
    def __init__(self):
        self.state = PipelineState()
        self._websockets: set[WebSocket] = set()
        self._save_lock = threading.Lock()

    def load(self):
        """Load state from JSON file, or initialize with default agents."""
        os.makedirs(DATA_DIR, exist_ok=True)
        os.makedirs(WORKSPACES_DIR, exist_ok=True)

        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                self.state = PipelineState.model_validate_json(f.read())

        # Ensure all configured agents exist
        for agent_def in AGENTS:
            if agent_def["name"] not in self.state.agents:
                self.state.agents[agent_def["name"]] = AgentConfig(**agent_def)

    def save(self):
        """Atomically write state to JSON file (thread-safe)."""
        with self._save_lock:
            os.makedirs(DATA_DIR, exist_ok=True)
            tmp = STATE_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(self.state.model_dump_json(indent=2))
            # Retry os.replace on Windows — file may be briefly locked by antivirus/indexer
            for attempt in range(3):
                try:
                    os.replace(tmp, STATE_FILE)
                    return
                except PermissionError:
                    if attempt < 2:
                        time.sleep(0.1 * (attempt + 1))
                    else:
                        raise

    # --- Projects ---

    def add_project(self, name: str, description: str = "", repo_url: str = None) -> Project:
        project = Project(name=name, description=description, repo_url=repo_url)
        self.state.projects[project.id] = project
        os.makedirs(self.get_project_workspace(project.id), exist_ok=True)
        self.save()
        return project

    def remove_project(self, project_id: str) -> bool:
        if project_id in self.state.projects:
            del self.state.projects[project_id]
            # Remove associated tasks
            to_remove = [tid for tid, t in self.state.tasks.items() if t.project_id == project_id]
            for tid in to_remove:
                del self.state.tasks[tid]
            self.save()
            return True
        return False

    def get_project_workspace(self, project_id: str) -> str:
        return os.path.join(WORKSPACES_DIR, project_id)

    # --- Tasks ---

    def add_task(self, project_id: str, title: str, description: str, priority: str = "medium") -> Task:
        try:
            prio = TaskPriority(priority.lower())
        except ValueError:
            prio = TaskPriority.MEDIUM
        task = Task(project_id=project_id, title=title, description=description, priority=prio)
        self.state.tasks[task.id] = task
        self.save()
        return task

    def remove_task(self, task_id: str) -> bool:
        if task_id in self.state.tasks:
            task = self.state.tasks[task_id]
            # Free agent if assigned
            if task.assigned_agent:
                self.free_agent(task.assigned_agent)
            del self.state.tasks[task_id]
            self.save()
            return True
        return False

    def reset_task(self, task_id: str) -> bool:
        task = self.state.tasks.get(task_id)
        if not task:
            return False
        if task.assigned_agent and task.assigned_agent in self.state.agents:
            self.free_agent(task.assigned_agent)
        task.stage = PipelineStage.INBOX
        task.assigned_agent = None
        task.retries = 0
        task.updated_at = _now()
        self.save()
        return True

    def get_tasks_by_stage(self, stage: PipelineStage, project_id: str = None) -> list[Task]:
        tasks = [t for t in self.state.tasks.values() if t.stage == stage]
        if project_id:
            tasks = [t for t in tasks if t.project_id == project_id]
        return tasks

    def get_available_agents(self, role: AgentRole) -> list[AgentConfig]:
        return [
            a for a in self.state.agents.values()
            if a.role == role and not a.is_busy
        ]

    # --- Agent management ---

    def assign_agent(self, task: Task, agent: AgentConfig):
        agent.is_busy = True
        agent.current_task_id = task.id
        agent.location = STAGE_LOCATION_MAP.get(task.stage, AgentLocation.CAFETERIA)
        task.assigned_agent = agent.name
        task.updated_at = _now()
        self.save()

    def free_agent(self, agent_name: str):
        agent = self.state.agents.get(agent_name)
        if agent:
            agent.is_busy = False
            agent.current_task_id = None
            agent.location = AgentLocation.CAFETERIA
            self.save()

    def move_agent(self, agent_name: str, location: AgentLocation):
        agent = self.state.agents.get(agent_name)
        if agent:
            agent.location = location
            self.save()

    def advance_task(self, task_id: str, new_stage: PipelineStage, agent_name: str, message: str, **fields):
        task = self.state.tasks.get(task_id)
        if not task:
            return
        task.stage = new_stage
        task.assigned_agent = None
        task.updated_at = _now()
        task.history.append(LogEntry(agent_name=agent_name, stage=new_stage, message=message))
        for key, val in fields.items():
            if hasattr(task, key):
                setattr(task, key, val)
        self.free_agent(agent_name)
        self.save()

    # --- Planning failure tracking ---

    def record_planning_failure(self, task_id: str):
        """Record a planning failure for a task. Persists to disk."""
        failure = self.state.planning_failures.get(task_id)
        if failure:
            failure.fail_count += 1
            failure.last_failure_at = _now()
        else:
            self.state.planning_failures[task_id] = PlanningFailure(fail_count=1, last_failure_at=_now())
        self.save()

    def get_planning_failure(self, task_id: str) -> Optional[PlanningFailure]:
        """Get planning failure record for a task, or None."""
        return self.state.planning_failures.get(task_id)

    def cleanup_stale_planning_failures(self, max_age_hours: int = 24):
        """Remove failure records older than max_age_hours or for deleted tasks."""
        now = datetime.now(timezone.utc)
        stale = []
        for task_id, failure in self.state.planning_failures.items():
            # Remove if task no longer exists
            if task_id not in self.state.tasks:
                stale.append(task_id)
                continue
            # Remove if older than max_age_hours
            try:
                last_fail = datetime.fromisoformat(failure.last_failure_at)
                age_hours = (now - last_fail).total_seconds() / 3600
                if age_hours > max_age_hours:
                    stale.append(task_id)
            except (ValueError, TypeError):
                stale.append(task_id)
        if stale:
            for task_id in stale:
                del self.state.planning_failures[task_id]
            self.save()

    # --- State access ---

    def get_state_json(self) -> str:
        return self.state.model_dump_json()

    # --- WebSocket management ---

    def register_ws(self, ws: WebSocket):
        self._websockets.add(ws)

    def unregister_ws(self, ws: WebSocket):
        self._websockets.discard(ws)

    async def broadcast(self):
        """Send current state to all connected WebSocket clients."""
        data = self.get_state_json()
        dead = set()
        for ws in self._websockets:
            try:
                await ws.send_text(data)
            except Exception:
                dead.add(ws)
        self._websockets -= dead
