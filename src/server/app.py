"""FastAPI Application for AgentCore Web Dashboard & API.
Provides task management, live DAG tracking, budget monitoring, and artifact inspection.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from decimal import Decimal
from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src.core.engine import AgentCoreEngine
from src.core.task import TaskInput
from src.core.modes import ExecutionMode
from src.core.executor import FakeExecutor
from src.adapters.provider import MultiProviderExecutor
from src.models.registry import ModelRegistry
from src.checkpoint.manager import CheckpointManager
from src.checkpoint.manifest import TaskManifest
from src.observability.manifest_view import budget_view, manifest_prompt, task_summary


app = FastAPI(
    title="AgentCore Dashboard API",
    description="Provider-Agnostic, Budget-Aware AI Agent Execution Engine API",
    version="3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global engine registry for active sessions
_active_engines: Dict[str, AgentCoreEngine] = {}
_shared_model_registry = ModelRegistry()


def get_or_create_engine(
    task_id: str,
    provider: str = "multi",
    repo_root: str = ".",
    checkpoint_dir: str = ".agentcore/checkpoints",
) -> AgentCoreEngine:
    """Returns existing active engine or creates a new engine instance for the task."""
    if task_id in _active_engines:
        return _active_engines[task_id]

    if provider == "fake":
        executor = FakeExecutor()
    else:
        executor = MultiProviderExecutor()

    engine = AgentCoreEngine(
        checkpoint_dir=checkpoint_dir,
        executor=executor,
        model_registry=_shared_model_registry,
        repo_root=repo_root,
    )
    _active_engines[task_id] = engine
    return engine


class TaskCreateRequest(BaseModel):
    task_id: Optional[str] = None
    prompt: str = Field(..., description="Goal prompt for the AI Agent")
    repository: Optional[str] = Field(None, description="Path to codebase repository")
    files: Optional[List[str]] = Field(default_factory=list, description="Document/Media file paths")
    budget: float = Field(10.0, description="Budget amount in USD")
    budget_unit: str = Field("USD", description="Currency/Unit for budget")
    execution_mode: str = Field("AUTO", description="Execution mode: AUTO, FULL, CREDIT_SAFE")
    provider: str = Field("multi", description="Executor provider: multi, fake, ollama")
    resume_task_id: Optional[str] = None


@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "engine": "AgentCore",
        "version": "3.0",
        "active_tasks": len(_active_engines),
    }


@app.get("/api/models")
async def list_models():
    """Lists all available models in the registry."""
    models = _shared_model_registry.list_enabled()
    return {
        "models": [
            {
                "model_id": m.model_id,
                "provider": m.provider,
                "tier": m.tier,
                "input_price_per_1k": float(m.input_price),
                "output_price_per_1k": float(m.output_price),
                "capabilities": m.capabilities,
                "context_size": m.context_size,
            }
            for m in models
        ]
    }


@app.get("/api/tasks")
async def list_tasks():
    """Lists active and checkpointed tasks."""
    checkpoint_dir = ".agentcore/checkpoints"
    tasks_summary = []
    seen = set()

    for task_id in _active_engines:
        engine = _active_engines[task_id]
        manifest = engine.current_manifest
        if manifest:
            seen.add(task_id)
            tasks_summary.append(task_summary(manifest, active_in_memory=True))

    if os.path.exists(checkpoint_dir):
        for fname in os.listdir(checkpoint_dir):
            if fname.endswith("_manifest.json"):
                fpath = os.path.join(checkpoint_dir, fname)
                try:
                    m = TaskManifest.load(fpath)
                    if m.task_id not in seen:
                        seen.add(m.task_id)
                        tasks_summary.append(task_summary(m, active_in_memory=False))
                except Exception:
                    continue

    tasks_summary.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
    return {"tasks": tasks_summary}


@app.post("/api/tasks")
async def create_task(req: TaskCreateRequest):
    """Initializes a new AgentCore task or prepares resume from checkpoint."""
    import uuid
    task_id = req.task_id or f"task_{uuid.uuid4().hex[:8]}"

    mode_map = {
        "AUTO": ExecutionMode.AUTO,
        "FULL": ExecutionMode.FULL,
        "CREDIT_SAFE": ExecutionMode.CREDIT_SAFE,
    }
    mode = mode_map.get(req.execution_mode.upper(), ExecutionMode.AUTO)

    engine = get_or_create_engine(task_id=task_id, provider=req.provider)

    task_input = TaskInput(
        task_id=task_id,
        prompt=req.prompt,
        repository=req.repository,
        files=req.files or [],
        budget=req.budget,
        budget_unit=req.budget_unit,
        execution_mode=mode,
        resume_task_id=req.resume_task_id,
    )

    manifest = engine.initialize_task(task_input)
    manifest.orchestration["source"] = "local_web"
    if engine.current_context:
        engine.current_context.orchestration["source"] = "local_web"
    engine.checkpoint_manager.save_checkpoint(manifest)

    return {
        "task_id": task_id,
        "status": manifest.status,
        "manifest": manifest.to_dict(),
        "work_units": [u.to_dict() for u in engine.work_units],
        "budget_info": manifest.budget_info,
    }


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    """Retrieves full state, DAG work units, and budget details for a task."""
    engine = _active_engines.get(task_id)
    if not engine:
        checkpoint_mgr = CheckpointManager(".agentcore/checkpoints")
        manifest = checkpoint_mgr.load_checkpoint(task_id)
        if not manifest:
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")
        return {
            "task_id": task_id,
            "status": manifest.status,
            "manifest": manifest.to_dict(),
            "work_units": manifest.work_units_data,
            "budget_info": budget_view(manifest),
            "outputs": manifest.outputs,
            "model_history": manifest.model_history,
            "errors": manifest.errors,
        }

    manifest = engine.current_manifest
    return {
        "task_id": task_id,
        "status": manifest.status if manifest else "initialized",
        "manifest": manifest.to_dict() if manifest else None,
        "work_units": [u.to_dict() for u in engine.work_units],
        "budget_info": budget_view(manifest) if manifest else {},
        "outputs": manifest.outputs if manifest else [],
        "model_history": manifest.model_history if manifest else [],
        "errors": manifest.errors if manifest else [],
    }


@app.post("/api/tasks/{task_id}/step")
async def step_task(task_id: str):
    """Executes the next single WorkUnit in the task DAG."""
    engine = _active_engines.get(task_id)
    if not engine:
        # Load from checkpoint
        checkpoint_mgr = CheckpointManager(".agentcore/checkpoints")
        manifest = checkpoint_mgr.load_checkpoint(task_id)
        if not manifest:
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")
        engine = get_or_create_engine(task_id=task_id)
        prompt_text = manifest_prompt(manifest)
        task_input = TaskInput(
            task_id=task_id,
            prompt=prompt_text,
            resume_task_id=task_id,
        )
        engine.initialize_task(task_input)

    more_units = await run_in_threadpool(engine.run_next_unit)
    manifest = engine.current_manifest

    return {
        "task_id": task_id,
        "more_units_remaining": more_units,
        "status": manifest.status if manifest else "running",
        "manifest": manifest.to_dict() if manifest else None,
        "work_units": [u.to_dict() for u in engine.work_units],
        "budget_info": budget_view(manifest) if manifest else {},
        "outputs": manifest.outputs if manifest else [],
        "errors": manifest.errors if manifest else [],
    }


@app.post("/api/tasks/{task_id}/run")
async def run_task_to_completion(task_id: str):
    """Executes all remaining WorkUnits in the task until completion."""
    engine = _active_engines.get(task_id)
    if not engine:
        checkpoint_mgr = CheckpointManager(".agentcore/checkpoints")
        manifest = checkpoint_mgr.load_checkpoint(task_id)
        if not manifest:
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")
        engine = get_or_create_engine(task_id=task_id)
        prompt_text = manifest_prompt(manifest)
        task_input = TaskInput(
            task_id=task_id,
            prompt=prompt_text,
            resume_task_id=task_id,
        )
        engine.initialize_task(task_input)

    # Keep the ASGI event loop free so the dashboard can poll checkpoints while
    # a synchronous provider/executor is running.
    report = await run_in_threadpool(engine.run_to_completion)
    manifest = engine.current_manifest

    return {
        "task_id": task_id,
        "report": report,
        "status": manifest.status if manifest else "completed",
        "manifest": manifest.to_dict() if manifest else None,
        "work_units": [u.to_dict() for u in engine.work_units],
        "budget_info": budget_view(manifest) if manifest else {},
        "outputs": manifest.outputs if manifest else [],
    }


@app.get("/api/tasks/{task_id}/artifacts/{artifact_path:path}")
async def get_artifact(task_id: str, artifact_path: str):
    """Retrieve only a file explicitly recorded in this task's manifest."""
    engine = _active_engines.get(task_id)
    manifest = engine.current_manifest if engine else CheckpointManager(".agentcore/checkpoints").load_checkpoint(task_id)
    if not manifest:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")

    requested = Path(artifact_path).resolve()
    allowed = {Path(path).resolve() for path in manifest.outputs}
    if requested not in allowed:
        raise HTTPException(status_code=403, detail="Artifact is not registered for this task")
    if not requested.exists() or not requested.is_file():
        raise HTTPException(status_code=404, detail="Artifact file not found")

    try:
        with requested.open("r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return {
            "path": artifact_path,
            "filename": requested.name,
            "content": content,
            "size_bytes": requested.stat().st_size,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Mount static directory for Web Dashboard UI
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    async def index():
        return FileResponse(os.path.join(static_dir, "index.html"))
