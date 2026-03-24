import asyncio
import uvicorn
from pipeline import PipelineOrchestrator
from api import app, set_store
from store import StateStore
from config import HOST, PORT, WORKSPACES_DIR, DATA_DIR
import os


async def main():
    # Ensure directories exist
    os.makedirs(WORKSPACES_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)

    # Initialize store
    store = StateStore()
    store.load()
    set_store(store)
    print(f"[main] Loaded {len(store.state.projects)} projects, {len(store.state.tasks)} tasks, {len(store.state.agents)} agents")

    # Create orchestrator
    orchestrator = PipelineOrchestrator(store)

    # Run pipeline + web server concurrently
    config = uvicorn.Config(app, host=HOST, port=PORT, log_level="info")
    server = uvicorn.Server(config)

    print(f"[main] Dashboard: http://localhost:{PORT}")
    print(f"[main] Workspaces: {WORKSPACES_DIR}")
    print("[main] Press Ctrl+C to stop\n")

    await asyncio.gather(
        orchestrator.run(),
        server.serve(),
    )


if __name__ == "__main__":
    asyncio.run(main())
