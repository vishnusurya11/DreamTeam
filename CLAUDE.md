# CLAUDE.md — Project Instructions for Claude Code

## Git & GitHub Rules

- **NEVER merge a PR without explicit user approval.** Always stop after creating the PR and wait for the user to review and approve.
- **NEVER push directly to `master`.** Always work on feature branches.
- **NEVER delete branches** without explicit user approval.
- **NEVER force push** without explicit user approval.
- After creating a PR, share the link and wait for instructions before taking any further action on it.

## Workflow

1. Read the issue and sub-issues thoroughly before starting work.
2. Create a feature branch from `master`.
3. Break down work into small, trackable tasks.
4. Comment on each issue/sub-issue with implementation details as you go.
5. Commit with clear messages referencing issue numbers.
6. Push the branch and create a PR.
7. **STOP and wait for user approval before merging.**
8. After user approves and merge is done, close all related issues.
9. Delete the branch only when user confirms.

## Code Style

- Python 3.12, type hints preferred.
- Use Pydantic BaseModel for data structures.
- Keep functions small and focused.
- No unnecessary dependencies.

## Project Context

- This is DreamTeam — an autonomous AI software engineering team simulator.
- Backend: FastAPI + LangChain/LangGraph + Pydantic.
- Frontend: Vanilla HTML/CSS/JS single-page app in `static/index.html`.
- State persisted to `data/state.json`.
- Agent tools are in `tool_plugins/` (auto-discovered).
