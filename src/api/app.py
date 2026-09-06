"""Small production-oriented HTTP API around AgentCoreEngine.

Run with: uvicorn src.api.app:app --reload
The API executes synchronously so the checkpoint is durable before the response.
For long-running workloads, callers can use the checkpoint ID to resume.
"""
from typing import Any, Dict, List, Optional
import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.adapters.provider import MultiProviderExecutor
from src.checkpoint.manager import CheckpointManager
from src.core.engine import AgentCoreEngine
from src.core.modes import ExecutionMode
from src.core.task import TaskInput
from src.models.registry import ModelRegistry


class RunRequest(BaseModel):
    prompt: str = Field(min_length=1)
    task_id: Optional[str] = None
    repository: Optional[str] = "."
    files: List[str] = Field(default_factory=list)
    budget: float = Field(default=5.0, gt=0)
    mode: str = Field(default="AUTO", pattern="^(AUTO|FULL|CREDIT_SAFE)$")
    output_type: str = "text"


class RunResponse(BaseModel):
    task_id: str
    status: str
    report: str
    outputs: List[str] = Field(default_factory=list)


app = FastAPI(title="AgentCore API", version="1.0.0")


def _engine(repository: str) -> AgentCoreEngine:
    timeout = float(os.getenv("AGENTCORE_TIMEOUT_SECONDS", "60"))
    return AgentCoreEngine(
        executor=MultiProviderExecutor(timeout_seconds=timeout),
        repo_root=repository,
    )


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "agentcore"}


@app.get("/models")
def models() -> List[Dict[str, Any]]:
    return [
        {
            "provider": model.provider,
            "model_id": model.model_id,
            "tier": model.tier,
            "input_price_per_1k": str(model.input_price),
            "output_price_per_1k": str(model.output_price),
            "capabilities": model.capabilities,
            "enabled": model.enabled,
        }
        for model in ModelRegistry().list_enabled()
    ]


@app.post("/run", response_model=RunResponse)
def run_task(request: RunRequest) -> RunResponse:
    task_id = request.task_id or "api_task_" + os.urandom(4).hex()
    try:
        engine = _engine(request.repository or ".")
        task = TaskInput(
            task_id=task_id,
            prompt=request.prompt,
            repository=request.repository,
            files=request.files,
            output_type=request.output_type,
            budget=request.budget,
            execution_mode=ExecutionMode[request.mode],
        )
        manifest = engine.initialize_task(task)
        report = engine.run_to_completion()
        return RunResponse(
            task_id=task_id,
            status=engine.current_manifest.status if engine.current_manifest else manifest.status,
            report=report,
            outputs=engine.current_manifest.outputs if engine.current_manifest else manifest.outputs,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/tasks/{task_id}")
def task_status(task_id: str) -> Dict[str, Any]:
    manifest = CheckpointManager(".agentcore/checkpoints").load_checkpoint(task_id)
    if not manifest:
        raise HTTPException(status_code=404, detail="Task not found")
    return manifest.to_dict()
