import importlib
import os
import pkgutil
import subprocess
from langchain_core.tools import tool


def discover_tools(role: str) -> list:
    """Auto-discover tools from the tools/ package that are available for a given role."""
    discovered = []
    tools_dir = os.path.join(os.path.dirname(__file__), "tool_plugins")
    if not os.path.isdir(tools_dir):
        return discovered

    for importer, modname, ispkg in pkgutil.iter_modules([tools_dir]):
        if modname.startswith("_"):
            continue
        try:
            mod = importlib.import_module(f"tool_plugins.{modname}")
            tools_list = getattr(mod, "TOOLS", [])
            roles = getattr(mod, "ROLES", None)  # None = all roles
            if roles is None or role in roles:
                discovered.extend(tools_list)
        except Exception as e:
            print(f"[tools] Warning: Failed to load tools/{modname}: {e}")
    return discovered


def _safe_path(workspace_dir: str, path: str) -> str:
    """Resolve path within workspace, prevent directory traversal."""
    resolved = os.path.normpath(os.path.join(workspace_dir, path))
    if not resolved.startswith(os.path.normpath(workspace_dir)):
        raise ValueError(f"Path '{path}' escapes workspace directory")
    return resolved


def make_workspace_tools(workspace_dir: str) -> dict:
    """Create file tools bound to a specific project workspace."""
    os.makedirs(workspace_dir, exist_ok=True)

    @tool
    def write_file(path: str, content: str) -> str:
        """Write content to a file in the workspace.

        Args:
            path: Relative file path within the workspace (e.g., 'main.py')
            content: The content to write to the file
        """
        full_path = _safe_path(workspace_dir, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote {len(content)} chars to {path}"

    @tool
    def read_file(path: str) -> str:
        """Read content from a file in the workspace.

        Args:
            path: Relative file path within the workspace
        """
        full_path = _safe_path(workspace_dir, path)
        if not os.path.exists(full_path):
            return f"Error: File '{path}' does not exist"
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()

    @tool
    def list_files(directory: str = ".") -> str:
        """List files and directories in the workspace.

        Args:
            directory: Relative directory path within workspace (default: root)
        """
        full_path = _safe_path(workspace_dir, directory)
        if not os.path.isdir(full_path):
            return f"Error: '{directory}' is not a directory"
        entries = []
        for root, dirs, files in os.walk(full_path):
            rel_root = os.path.relpath(root, workspace_dir)
            for f in files:
                entries.append(os.path.join(rel_root, f))
        if not entries:
            return "Workspace is empty"
        return "\n".join(sorted(entries))

    @tool
    def execute_python(code: str) -> str:
        """Execute Python code and return the output.

        Args:
            code: Python code to execute
        """
        try:
            result = subprocess.run(
                ["python", "-c", code],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=workspace_dir,
            )
            output = ""
            if result.stdout:
                output += result.stdout
            if result.stderr:
                output += f"\nSTDERR:\n{result.stderr}"
            if result.returncode != 0:
                output += f"\nExit code: {result.returncode}"
            return output.strip() or "Code executed successfully (no output)"
        except subprocess.TimeoutExpired:
            return "Error: Code execution timed out (30s limit)"
        except Exception as e:
            return f"Error executing code: {e}"

    return {
        "write_file": write_file,
        "read_file": read_file,
        "list_files": list_files,
        "execute_python": execute_python,
    }


def make_planning_tools(store, project_id: str) -> list:
    """Create planning-specific tools bound to a project."""
    from models import Task, PipelineStage, TaskPriority

    @tool
    def create_subtask(parent_task_id: str, title: str, description: str, priority: str = "medium") -> str:
        """Create a subtask under a parent task. Used during planning to break features into dev tasks.

        Args:
            parent_task_id: The ID of the parent task being decomposed
            title: Short title for the subtask
            description: Detailed description of what needs to be built
            priority: Priority level (critical, high, medium, low)
        """
        parent = store.state.tasks.get(parent_task_id)
        if not parent:
            return f"Error: Parent task '{parent_task_id}' not found"
        try:
            prio = TaskPriority(priority.lower())
        except ValueError:
            prio = TaskPriority.MEDIUM

        subtask = Task(
            project_id=project_id,
            title=title,
            description=description,
            priority=prio,
            stage=PipelineStage.BACKLOG,
            parent_task_id=parent_task_id,
        )
        store.state.tasks[subtask.id] = subtask
        parent.subtask_ids.append(subtask.id)
        store.save()
        return f"Created subtask '{title}' (id: {subtask.id}) with priority {priority}"

    @tool
    def set_priority(task_id: str, priority: str) -> str:
        """Set or change the priority of a task.

        Args:
            task_id: The task ID to update
            priority: New priority (critical, high, medium, low)
        """
        task = store.state.tasks.get(task_id)
        if not task:
            return f"Error: Task '{task_id}' not found"
        try:
            task.priority = TaskPriority(priority.lower())
        except ValueError:
            return f"Error: Invalid priority '{priority}'. Use: critical, high, medium, low"
        store.save()
        return f"Set priority of '{task.title}' to {priority}"

    @tool
    def add_notes(task_id: str, notes: str) -> str:
        """Add planning notes to a task (analysis, risks, dependencies, acceptance criteria).

        Args:
            task_id: The task ID to add notes to
            notes: Planning notes text
        """
        task = store.state.tasks.get(task_id)
        if not task:
            return f"Error: Task '{task_id}' not found"
        if task.planning_notes:
            task.planning_notes += f"\n\n{notes}"
        else:
            task.planning_notes = notes
        store.save()
        return f"Added planning notes to '{task.title}'"

    @tool
    def list_project_tasks(status: str = "all") -> str:
        """List existing tasks in the current project for context.

        Args:
            status: Filter by stage (e.g., 'INBOX', 'BACKLOG', 'BUILDING') or 'all'
        """
        tasks = [t for t in store.state.tasks.values() if t.project_id == project_id]
        if status != "all":
            tasks = [t for t in tasks if t.stage == status.upper()]
        if not tasks:
            return "No tasks found"
        lines = []
        for t in tasks:
            lines.append(f"[{t.id}] {t.title} | stage={t.stage} priority={t.priority}")
        return "\n".join(lines)

    return [create_subtask, set_priority, add_notes, list_project_tasks]


def get_tools_for_role(role: str, workspace_dir: str, store=None, project_id: str = None) -> list:
    """Return the appropriate tool set for an agent role, including auto-discovered tools."""
    # Base tools per role
    if role == "planner":
        base_tools = make_planning_tools(store, project_id)
    elif role == "builder":
        ws = make_workspace_tools(workspace_dir)
        base_tools = [ws["write_file"], ws["read_file"], ws["list_files"], ws["execute_python"]]
    elif role == "qa":
        ws = make_workspace_tools(workspace_dir)
        base_tools = [ws["read_file"], ws["list_files"], ws["execute_python"]]
    elif role == "reviewer":
        ws = make_workspace_tools(workspace_dir)
        base_tools = [ws["read_file"], ws["list_files"]]
    else:
        base_tools = []

    # Add auto-discovered tools from tools/ folder
    extra_tools = discover_tools(role)
    return base_tools + extra_tools
