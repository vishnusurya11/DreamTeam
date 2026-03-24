from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import os

app = FastAPI(title="DreamTeam")
_store = None

# Serve static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


def set_store(store):
    global _store
    _store = store


# --- Request models ---

class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    repo_url: Optional[str] = None


class TaskCreate(BaseModel):
    title: str
    description: str
    priority: str = "medium"


# --- Routes ---

@app.get("/")
async def index():
    return FileResponse(os.path.join(static_dir, "index.html"))


@app.get("/api/state")
async def get_state():
    return JSONResponse(content=_store.state.model_dump())


# --- Projects ---

@app.get("/api/projects")
async def list_projects():
    return JSONResponse(content=list(_store.state.projects.values()))


@app.post("/api/projects")
async def create_project(body: ProjectCreate):
    project = _store.add_project(body.name, body.description, body.repo_url)
    await _store.broadcast()
    return JSONResponse(content=project.model_dump())


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str):
    if _store.remove_project(project_id):
        await _store.broadcast()
        return {"ok": True}
    return JSONResponse(status_code=404, content={"error": "Project not found"})


# --- Tasks ---

@app.post("/api/projects/{project_id}/tasks")
async def create_task(project_id: str, body: TaskCreate):
    if project_id not in _store.state.projects:
        return JSONResponse(status_code=404, content={"error": "Project not found"})
    task = _store.add_task(project_id, body.title, body.description, body.priority)
    await _store.broadcast()
    return JSONResponse(content=task.model_dump())


@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    if _store.remove_task(task_id):
        await _store.broadcast()
        return {"ok": True}
    return JSONResponse(status_code=404, content={"error": "Task not found"})


@app.post("/api/tasks/{task_id}/reset")
async def reset_task(task_id: str):
    if _store.reset_task(task_id):
        await _store.broadcast()
        return {"ok": True}
    return JSONResponse(status_code=404, content={"error": "Task not found"})


# --- Agents ---

@app.get("/api/agents")
async def list_agents():
    return JSONResponse(content=list(_store.state.agents.values()))


# --- WebSocket ---

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _store.register_ws(ws)
    try:
        await ws.send_text(_store.get_state_json())
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _store.unregister_ws(ws)
