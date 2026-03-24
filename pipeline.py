import asyncio
import time
import traceback
from datetime import datetime, timezone
from models import AgentLocation, AgentRole, LogEntry, PipelineStage
from store import StateStore
from agents import run_agent_on_task
from config import TICK_INTERVAL_SECONDS, MAX_RETRIES

PLANNING_MAX_RETRIES = 3
PLANNING_COOLDOWN_SECONDS = 30


# Stages where dev tasks are waiting to be picked up
DEV_PICKUP_STAGES = [PipelineStage.BACKLOG, PipelineStage.QA, PipelineStage.REVIEW]

# Map pickup stage to the role that handles it
STAGE_ROLE_MAP = {
    PipelineStage.BACKLOG: AgentRole.BUILDER,
    PipelineStage.QA: AgentRole.QA,
    PipelineStage.REVIEW: AgentRole.REVIEWER,
}

# What stage a task moves to when picked up
STAGE_WORKING = {
    PipelineStage.BACKLOG: PipelineStage.BUILDING,
    PipelineStage.QA: PipelineStage.QA,
    PipelineStage.REVIEW: PipelineStage.REVIEW,
}

# Planner order for planning meetings
PLANNER_ORDER = ["Paula", "Alex", "Sam"]


class PipelineOrchestrator:
    def __init__(self, store: StateStore):
        self.store = store
        self._running_tasks: set[str] = set()
        self._planning_failures: dict[str, tuple[int, float]] = {}  # task_id -> (fail_count, last_fail_time)

    async def run(self):
        """Main pipeline loop."""
        print("[pipeline] Started pipeline orchestrator")
        while True:
            try:
                await self._tick()
            except Exception as e:
                print(f"[pipeline] Error in tick: {e}")
                traceback.print_exc()
            await asyncio.sleep(TICK_INTERVAL_SECONDS)

    async def _tick(self):
        """One pipeline cycle: planning + dev stages."""
        await self._tick_planning()
        await self._tick_development()

    # --- Planning Phase ---

    async def _tick_planning(self):
        """Pick up INBOX tasks and run planning meetings."""
        now = time.monotonic()
        inbox_tasks = []
        for t in self.store.get_tasks_by_stage(PipelineStage.INBOX):
            if t.assigned_agent is not None or t.id in self._running_tasks or t.parent_task_id is not None:
                continue
            # Check planning failure cooldown
            fail_info = self._planning_failures.get(t.id)
            if fail_info:
                fail_count, last_fail = fail_info
                if fail_count >= PLANNING_MAX_RETRIES:
                    continue  # Exhausted retries, skip
                if now - last_fail < PLANNING_COOLDOWN_SECONDS:
                    continue  # In cooldown, skip
            inbox_tasks.append(t)
        if not inbox_tasks:
            return

        # Check if all planners are available
        planners = self.store.get_available_agents(AgentRole.PLANNER)
        planner_names = {p.name for p in planners}
        if not all(name in planner_names for name in PLANNER_ORDER):
            return  # Need all planners available for a meeting

        # Take the highest-priority inbox task
        inbox_tasks.sort(key=lambda t: list(["critical", "high", "medium", "low"]).index(t.priority))
        task = inbox_tasks[0]

        # Mark task as being planned
        task.stage = PipelineStage.PLANNING
        self._running_tasks.add(task.id)
        self.store.save()
        await self.store.broadcast()

        print(f"[pipeline] Planning meeting started for '{task.title}'")
        asyncio.create_task(self._execute_planning(task.id))

    async def _execute_planning(self, task_id: str):
        """Run a planning meeting: Paula -> Alex -> Sam sequentially."""
        task = self.store.state.tasks.get(task_id)
        if not task:
            self._running_tasks.discard(task_id)
            return

        project = self.store.state.projects.get(task.project_id)
        workspace_dir = self.store.get_project_workspace(task.project_id) if project else ""

        try:
            # Move all planners to meeting room
            for name in PLANNER_ORDER:
                agent = self.store.state.agents.get(name)
                if agent:
                    agent.is_busy = True
                    agent.current_task_id = task_id
                    agent.location = AgentLocation.MEETING_ROOM
            task.assigned_agent = "Planning Team"
            self.store.save()
            await self.store.broadcast()

            # Run planners sequentially
            accumulated_context = ""
            for planner_name in PLANNER_ORDER:
                agent = self.store.state.agents.get(planner_name)
                if not agent:
                    continue

                print(f"[pipeline] {planner_name} analyzing '{task.title}'...")

                # Add accumulated context to planning notes temporarily
                if accumulated_context:
                    task.planning_notes = accumulated_context

                result = await run_agent_on_task(
                    agent, task, PipelineStage.PLANNING,
                    workspace_dir=workspace_dir,
                    store=self.store,
                    project_id=task.project_id,
                )
                accumulated_context += f"\n\n### {planner_name}'s Analysis:\n{result}"
                print(f"[pipeline] {planner_name} completed analysis")

            # Store final planning notes
            task.planning_notes = accumulated_context

            # Move parent task to BACKLOG (subtasks are already in BACKLOG via create_subtask tool)
            task.stage = PipelineStage.BACKLOG
            task.assigned_agent = None
            task.updated_at = datetime.now(timezone.utc).isoformat()
            task.history.append(
                LogEntry(
                    agent_name="Planning Team",
                    stage=PipelineStage.BACKLOG,
                    message=f"Planning complete. Created {len(task.subtask_ids)} subtasks.",
                )
            )

            # Free all planners
            for name in PLANNER_ORDER:
                self.store.free_agent(name)

            self.store.save()
            print(f"[pipeline] Planning complete for '{task.title}' -> BACKLOG")

        except Exception as e:
            # Track failure for cooldown/retry limiting
            fail_info = self._planning_failures.get(task_id, (0, 0))
            fail_count = fail_info[0] + 1
            self._planning_failures[task_id] = (fail_count, time.monotonic())
            print(f"[pipeline] Planning error for '{task.title}' (attempt {fail_count}/{PLANNING_MAX_RETRIES}): {e}")
            traceback.print_exc()
            # Reset task to INBOX on failure
            task.stage = PipelineStage.INBOX
            task.assigned_agent = None
            for name in PLANNER_ORDER:
                self.store.free_agent(name)
            self.store.save()

        finally:
            self._running_tasks.discard(task_id)
            await self.store.broadcast()

    # --- Development Phase ---

    async def _tick_development(self):
        """Assign available agents to waiting dev tasks."""
        for stage in DEV_PICKUP_STAGES:
            waiting_tasks = [
                t for t in self.store.get_tasks_by_stage(stage)
                if t.assigned_agent is None and t.id not in self._running_tasks
            ]
            if not waiting_tasks:
                continue

            # Sort by priority
            waiting_tasks.sort(key=lambda t: list(["critical", "high", "medium", "low"]).index(t.priority))

            role = STAGE_ROLE_MAP[stage]
            available_agents = self.store.get_available_agents(role)

            for task in waiting_tasks:
                if not available_agents:
                    break
                agent = available_agents.pop(0)
                working_stage = STAGE_WORKING[stage]
                task.stage = working_stage
                self.store.assign_agent(task, agent)
                self._running_tasks.add(task.id)
                print(f"[pipeline] {agent.name} picked up '{task.title}' -> {working_stage}")
                await self.store.broadcast()
                asyncio.create_task(self._execute_dev_stage(task.id, agent.name, working_stage))

    async def _execute_dev_stage(self, task_id: str, agent_name: str, stage: PipelineStage):
        """Run an agent on a dev task and handle the result."""
        task = self.store.state.tasks.get(task_id)
        agent = self.store.state.agents.get(agent_name)
        if not task or not agent:
            self._running_tasks.discard(task_id)
            return

        workspace_dir = self.store.get_project_workspace(task.project_id)

        try:
            print(f"[pipeline] {agent_name} working on '{task.title}' ({stage})...")
            result = await run_agent_on_task(
                agent, task, stage,
                workspace_dir=workspace_dir,
                store=self.store,
                project_id=task.project_id,
            )
            print(f"[pipeline] {agent_name} finished '{task.title}' ({stage})")
            await self._handle_dev_result(task_id, agent_name, stage, result)
        except Exception as e:
            print(f"[pipeline] Error: {agent_name} failed on '{task.title}': {e}")
            traceback.print_exc()
            self.store.advance_task(
                task_id, PipelineStage.BACKLOG, agent_name,
                f"Agent error: {e}"
            )
        finally:
            self._running_tasks.discard(task_id)
            await self.store.broadcast()

    async def _handle_dev_result(self, task_id: str, agent_name: str, stage: PipelineStage, result: str):
        """Determine next stage based on agent output."""
        task = self.store.state.tasks.get(task_id)
        if not task:
            return

        if stage == PipelineStage.BUILDING:
            self.store.advance_task(
                task_id, PipelineStage.QA, agent_name,
                f"Build complete: {result[:500]}",
                code_output=result,
            )
            print(f"[pipeline] '{task.title}' -> QA")

        elif stage == PipelineStage.QA:
            verdict = result[-200:].upper()
            if "PASS" in verdict and "FAIL" not in verdict:
                self.store.advance_task(
                    task_id, PipelineStage.REVIEW, agent_name,
                    f"QA passed: {result[:500]}",
                    qa_report=result,
                )
                print(f"[pipeline] '{task.title}' -> REVIEW")
            else:
                task.retries += 1
                if task.retries >= MAX_RETRIES:
                    self.store.advance_task(
                        task_id, PipelineStage.SHIP, agent_name,
                        f"Max retries reached. Last QA: {result[:500]}",
                        qa_report=result,
                    )
                    print(f"[pipeline] '{task.title}' -> SHIP (max retries)")
                else:
                    self.store.advance_task(
                        task_id, PipelineStage.BACKLOG, agent_name,
                        f"QA failed (retry {task.retries}/{MAX_RETRIES}): {result[:500]}",
                        qa_report=result,
                    )
                    print(f"[pipeline] '{task.title}' -> BACKLOG (QA failed)")

        elif stage == PipelineStage.REVIEW:
            verdict = result[-200:].upper()
            if "APPROVE" in verdict and "REQUEST_CHANGES" not in verdict:
                self.store.advance_task(
                    task_id, PipelineStage.SHIP, agent_name,
                    f"Approved: {result[:500]}",
                    review_notes=result,
                )
                print(f"[pipeline] '{task.title}' -> SHIP (approved!)")
            else:
                task.retries += 1
                if task.retries >= MAX_RETRIES:
                    self.store.advance_task(
                        task_id, PipelineStage.SHIP, agent_name,
                        f"Max retries reached. Last review: {result[:500]}",
                        review_notes=result,
                    )
                    print(f"[pipeline] '{task.title}' -> SHIP (max retries)")
                else:
                    self.store.advance_task(
                        task_id, PipelineStage.BACKLOG, agent_name,
                        f"Changes requested (retry {task.retries}/{MAX_RETRIES}): {result[:500]}",
                        review_notes=result,
                    )
                    print(f"[pipeline] '{task.title}' -> BACKLOG (changes requested)")
