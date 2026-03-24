import asyncio
from langgraph.prebuilt import create_react_agent
from config import get_model
from models import AgentConfig, Task, PipelineStage
from tools import get_tools_for_role


STAGE_INSTRUCTIONS = {
    PipelineStage.PLANNING: (
        "You are in the PLANNING stage. Your job is to analyze and decompose this feature request.\n"
        "- Read the task title and description carefully\n"
        "- Use add_notes to record your analysis, risks, and recommendations\n"
        "- Use create_subtask to break the feature into 2-5 concrete, actionable dev tasks\n"
        "- Use set_priority to assign priorities to subtasks\n"
        "- Use list_project_tasks to see existing tasks for context\n"
        "- Each subtask should be small enough for one developer to complete\n"
        "- Include clear acceptance criteria in each subtask description\n"
        "- When done, summarize the plan you created"
    ),
    PipelineStage.BUILDING: (
        "You are in the BUILDING stage. Your job is to implement the task by writing code files.\n"
        "- Read the task description carefully\n"
        "- Write clean, working Python code using the write_file tool\n"
        "- Test your code using execute_python to make sure it runs\n"
        "- Create all necessary files for a complete implementation\n"
        "- When done, summarize what you built and which files you created"
    ),
    PipelineStage.QA: (
        "You are in the QA stage. Your job is to test the code that was built.\n"
        "- Use list_files and read_file to review all code in the workspace\n"
        "- Write test cases using execute_python\n"
        "- Run the tests and report findings\n"
        "- IMPORTANT: Your very last line MUST be exactly one of:\n"
        "  PASS\n"
        "  FAIL\n"
        "  Do not add anything after the verdict word."
    ),
    PipelineStage.REVIEW: (
        "You are in the REVIEW stage. Your job is to review the code quality.\n"
        "- Use list_files and read_file to examine all code and tests\n"
        "- Check for: bugs, security issues, code style, best practices, edge cases\n"
        "- IMPORTANT: Your very last line MUST be exactly one of:\n"
        "  APPROVE\n"
        "  REQUEST_CHANGES\n"
        "  Do not add anything after the verdict word."
    ),
}


def _build_prompt(agent_config: AgentConfig, task: Task, stage: PipelineStage) -> str:
    """Build the full prompt for an agent working on a task at a given stage."""
    instructions = STAGE_INSTRUCTIONS.get(stage, "")
    previous_context = ""
    if task.planning_notes:
        previous_context += f"\n\n## Planning Notes\n{task.planning_notes}"
    if task.code_output:
        previous_context += f"\n\n## Previous Build Output\n{task.code_output}"
    if task.qa_report:
        previous_context += f"\n\n## Previous QA Report\n{task.qa_report}"
    if task.review_notes:
        previous_context += f"\n\n## Previous Review Notes\n{task.review_notes}"

    return (
        f"## Task: {task.title}\n"
        f"Task ID: {task.id}\n\n"
        f"{task.description}\n\n"
        f"## Instructions\n{instructions}"
        f"{previous_context}"
    )


def create_agent_executor(agent_config: AgentConfig, workspace_dir: str, store=None, project_id: str = None):
    """Create a ReAct agent for the given agent config."""
    model = get_model()
    tools = get_tools_for_role(agent_config.role, workspace_dir, store=store, project_id=project_id)
    system_prompt = (
        f"You are {agent_config.name}, a {agent_config.role} on a software engineering team.\n"
        f"{agent_config.personality}\n"
        "Be concise and focused. Complete your task efficiently."
    )
    return create_react_agent(model, tools, prompt=system_prompt)


async def run_agent_on_task(
    agent_config: AgentConfig,
    task: Task,
    stage: PipelineStage,
    workspace_dir: str = "",
    store=None,
    project_id: str = None,
) -> str:
    """Run an agent on a task and return the result text."""
    agent = create_agent_executor(agent_config, workspace_dir, store=store, project_id=project_id)
    prompt = _build_prompt(agent_config, task, stage)

    def _invoke():
        response = agent.invoke({"messages": [{"role": "user", "content": prompt}]})
        return response["messages"][-1].content

    try:
        result = await asyncio.wait_for(asyncio.to_thread(_invoke), timeout=180)
    except asyncio.TimeoutError:
        return "FAIL: Agent timed out after 3 minutes."

    if isinstance(result, list):
        result = " ".join(str(item) for item in result)
    return result or "Agent completed without output."
