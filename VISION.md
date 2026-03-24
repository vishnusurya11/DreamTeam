# DreamTeam — Product Vision

## What Is This?

DreamTeam is a **virtual AI software engineering company** that runs autonomously. You feed it projects and tasks, and a team of AI agents — planners, developers, QA engineers, reviewers — work on them like a real engineering team operating in weekly sprints.

You watch them work in a **pixel-art virtual office** — walking between rooms, sitting at desks, holding planning meetings, running tests, reviewing code. It's your own software factory.

---

## The Team

### Planning Team (The War Room)
- **Paula** — Project Manager. Breaks epics into stories, defines acceptance criteria, manages scope.
- **Alex** — Software Architect. Decomposes features into technical tasks, identifies dependencies, designs system structure.
- **Sam** — Product Strategist. Prioritizes by user impact, flags risks, ensures the plan is practical.

When a new task comes in, all three convene in the **Meeting Room** and run a planning session:
1. Paula analyzes scope and user value
2. Alex breaks it into concrete technical subtasks
3. Sam reviews priorities and flags risks
4. Subtasks land in the backlog, ready for devs

### Dev Team
- **Charlie** — Senior Python Dev. Clean code, good naming, solid structure.
- **Codex** — Full-Stack Engineer. Architecture-minded, design patterns, maintainability.

### QA
- **Henry** — QA Engineer. Writes tests, runs them, finds edge cases. Either PASS or FAIL.

### Review
- **Ralph** — Code Reviewer. Checks for bugs, security issues, code style. Either APPROVE or REQUEST_CHANGES.

### Future Agents (not yet built)
- **DevOps agent** — Handles deployment, CI/CD, infrastructure
- **Documentation agent** — Writes docs, READMEs, API references
- **Research agent** — Deep web research before coding starts
- **Designer agent** — UI/UX mockups, wireframes
- **Security agent** — Security audits, vulnerability scanning

---

## The Pipeline

```
USER SUBMITS FEATURE/EPIC
        ↓
    ┌─────────┐
    │  INBOX  │  Raw feature requests land here
    └────┬────┘
         ↓
    ┌──────────┐
    │ PLANNING │  Paula + Alex + Sam hold a meeting
    │          │  Break into 2-5 subtasks
    └────┬─────┘
         ↓
    ┌──────────┐
    │ BACKLOG  │  Subtasks ready for dev team
    └────┬─────┘
         ↓
    ┌──────────┐
    │ BUILDING │  Charlie or Codex write the code
    └────┬─────┘
         ↓
    ┌──────────┐
    │    QA    │  Henry runs tests
    │          │  PASS → Review | FAIL → Back to Backlog
    └────┬─────┘
         ↓
    ┌──────────┐
    │  REVIEW  │  Ralph reviews code quality
    │          │  APPROVE → Ship | REQUEST_CHANGES → Back to Backlog
    └────┬─────┘
         ↓
    ┌──────────┐
    │   SHIP   │  Done. Delivered.
    └──────────┘
```

Max 3 retries per task. If a task fails QA or review 3 times, it ships anyway (with notes about what failed).

---

## The Office (UI)

A **top-down pixel-art virtual office** inspired by Pokemon/GameBoy indoor buildings and Gather.town.

### Rooms
- **Planning Room** — Whiteboard on wall, round table with chairs. Planners gather here during meetings.
- **Dev Area** — Multiple desks with monitors. Developers sit here when coding.
- **QA Lab** — Testing station with desk and monitor. Henry works here.
- **Review Room** — Large desk with two chairs facing each other. Ralph reviews here.
- **Meeting Room** — Large conference table with chairs around it. Planning meetings happen here.
- **Cafeteria** — Coffee machine, plants, small tables. Idle agents hang out here.

### Characters
- 16x16 pixel sprites (rendered via CSS box-shadow, no external assets)
- Each agent has unique colors (hair, shirt)
- Walking animation with alternating leg frames
- Status icons above their head: ⚡ working, 💤 idle
- A* pathfinding — they walk through doorways, not teleport
- Tile-by-tile movement at ~8fps

### UI Layout
```
┌──────────────────────────────────────────────────┐
│  DREAMTEAM HQ          [+ PROJECT] [+ TASK] LIVE │
├────────┬──────────────────────┬───────────────────┤
│        │                      │                   │
│  NAV   │   PIXEL ART OFFICE   │  CONTEXT PANEL   │
│        │                      │  (changes per     │
│ Office │   Characters walk    │   active tab)     │
│ Tasks  │   between rooms      │                   │
│ Agents │                      │  - Office info    │
│Pipeline│                      │  - Task list      │
│Projects│                      │  - Agent details  │
│Activity│                      │  - Pipeline flow  │
│ Stats  │                      │  - Project mgmt   │
│        │                      │  - Activity log   │
│ ────── │                      │  - Sprint stats   │
│ Agent  │                      │                   │
│ dots   │                      │                   │
├────────┴──────────────────────┴───────────────────┤
│  ✓ Shipped: 8  │ ⚡ Active: 14  │ Backlog: 3  │  │
└──────────────────────────────────────────────────┘
```

---

## Multi-Project Support

- Multiple projects, each with its own workspace directory
- Tasks belong to a project
- Agents work across projects (shared team)
- Per-project sandboxed file system (agents can't escape their workspace)
- Project selector in the UI

---

## Agent Tools

### Pluggable Tool System
Tools live in `tool_plugins/` folder. Drop a new `.py` file with `TOOLS` and `ROLES` exports — auto-discovered at startup.

### Current Tools
| Tool | Roles | Description |
|------|-------|-------------|
| `write_file` | builder | Write files to project workspace |
| `read_file` | builder, qa, reviewer | Read workspace files |
| `list_files` | builder, qa, reviewer | List workspace contents |
| `execute_python` | builder, qa | Run Python code (30s timeout) |
| `web_search` | all | DuckDuckGo web search |
| `web_search_news` | all | DuckDuckGo news search |
| `fetch_webpage` | planner, builder, qa | Fetch and extract text from URLs |
| `create_subtask` | planner | Create subtasks during planning |
| `set_priority` | planner | Set task priority |
| `add_notes` | planner | Add planning notes to tasks |
| `list_project_tasks` | planner | View existing tasks |

### Future Tools (not yet built)
- `git_clone` — Clone a repo into workspace
- `git_commit` / `git_push` — Version control operations
- `run_tests` — Run pytest/unittest in workspace
- `shell_command` — Execute arbitrary shell commands (sandboxed)
- `create_file_from_template` — Scaffolding
- `read_external_file` — Read files outside workspace (read-only)
- `call_api` — Make HTTP API calls
- `generate_image` — AI image generation for UI work
- `database_query` — Query project databases
- `send_notification` — Slack/Discord/email notifications when tasks complete

---

## LLM Backend

### Current
- **Ollama** (local) — Default. Uses whatever model you have installed (qwen3.5:9b, llama3.1:8b, etc.)
- **OpenRouter** (cloud) — Production option. Any model via API.
- LangChain + LangGraph for agent orchestration
- ReAct pattern: agents think → use tools → think → respond

### Future
- Per-agent model assignment (use a bigger model for planning, smaller for QA)
- Model fallback chains (try local first, fall back to cloud if timeout)
- Streaming agent output visible in the UI (watch them think in real-time)
- Agent memory — persistent context across tasks (learned patterns, project knowledge)
- Multi-model consensus — have two agents independently solve, then merge

---

## Sprint System (Future)

- Weekly sprint cycles with sprint planning, daily standups, retrospectives
- Sprint backlog vs product backlog separation
- Velocity tracking (tasks completed per sprint)
- Burndown charts in the Stats tab
- Sprint goals and acceptance criteria
- Auto-generated sprint reports

---

## Collaboration Features (Future)

- **Agent Chat** — Watch agents discuss tasks in a chat-like interface
- **Human-in-the-loop** — You can intervene, give feedback, redirect agents mid-task
- **Code Review UI** — See the actual diffs agents produce, approve/reject
- **Task Comments** — Add comments to tasks that agents will read
- **Approval Gates** — Require human approval before shipping

---

## Notifications & Integrations (Future)

- Webhook support for task state changes
- Slack/Discord bot notifications
- GitHub/GitLab integration (create PRs from shipped tasks)
- Jira/Linear sync (import tasks, export results)
- Email digests of daily/weekly activity

---

## Architecture

```
D:/Projects/DreamTeam/
├── main.py              # Async entry point (uvicorn + pipeline)
├── config.py            # LLM provider, agent definitions, constants
├── models.py            # Pydantic models (Project, Task, Agent, etc.)
├── store.py             # State persistence (JSON) + WebSocket broadcast
├── pipeline.py          # Two-phase orchestrator (planning + dev)
├── agents.py            # ReAct agent creation + stage prompts
├── tools.py             # Base tools + auto-discovery from tool_plugins/
├── api.py               # FastAPI routes + WebSocket endpoint
├── tool_plugins/        # Pluggable tools (drop .py files here)
│   ├── web_search.py    # DuckDuckGo search
│   └── web_scrape.py    # URL fetching
├── static/
│   └── index.html       # Complete frontend (single file)
├── workspaces/          # Per-project sandboxed directories
├── data/
│   └── state.json       # Persistent state
├── pyproject.toml       # Dependencies (uv managed)
└── .python-version      # Python 3.12
```

---

## Non-Goals (Things This Is NOT)

- Not a code editor or IDE
- Not a CI/CD pipeline (though it could trigger one)
- Not a replacement for human engineers (it's a force multiplier)
- Not trying to handle massive repos (focused on greenfield tasks and small-to-medium codebases)
- Not a chatbot — you give it tasks, it works autonomously

---

## Success Criteria

The dream state:
1. You wake up, open DreamTeam, create a project for your new SaaS idea
2. You describe 3-4 features as tasks
3. The planning team breaks them into 15-20 dev tasks
4. You go about your day
5. By evening, the dev team has built, tested, and reviewed the code
6. You review the shipped output, provide feedback on what to fix
7. Next morning, fixes are done
8. You have a working prototype in 2-3 days with zero coding from you
