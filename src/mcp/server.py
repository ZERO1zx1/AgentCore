"""Model Context Protocol (MCP) Server for AgentCore.
Enables external AI assistants (ChatGPT, Claude Desktop, Cursor, Antigravity)
to invoke AgentCore as an autonomous execution skill.
"""

import sys
import json
from typing import Dict, Any, Optional

from src.core.engine import AgentCoreEngine
from src.core.task import TaskInput
from src.core.modes import ExecutionMode
from src.core.executor import FakeExecutor
from src.adapters.provider import MultiProviderExecutor
from src.checkpoint.manager import CheckpointManager
from src.checkpoint.manifest import TaskManifest
from src.observability.manifest_view import budget_view, task_summary


# Tool definitions matching MCP specification
MCP_TOOLS = [
    {
        "name": "run_agentcore_task",
        "description": "Execute an autonomous, multi-step, budget-safe task on a codebase or files using AgentCore.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Goal or instruction for the autonomous agent",
                },
                "repository": {
                    "type": "string",
                    "description": "Local repository or project directory path (default: '.')",
                    "default": ".",
                },
                "budget": {
                    "type": "number",
                    "description": "Maximum budget limit in USD (default: 5.0)",
                    "default": 5.0,
                },
                "execution_mode": {
                    "type": "string",
                    "enum": ["AUTO", "FULL", "CREDIT_SAFE"],
                    "description": "Execution and cost routing mode",
                    "default": "AUTO",
                },
                "provider": {
                    "type": "string",
                    "enum": ["multi", "fake", "ollama"],
                    "description": "LLM provider backend",
                    "default": "multi",
                },
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional document or media attachments",
                    "default": [],
                },
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "get_agentcore_status",
        "description": "Retrieve current execution status, budget usage, and output artifacts for an AgentCore task.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "The unique task ID to check",
                }
            },
            "required": ["task_id"],
        },
    },
    {
        "name": "list_agentcore_checkpoints",
        "description": "List all saved task checkpoints and execution histories.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


def handle_run_task(args: Dict[str, Any]) -> Dict[str, Any]:
    """Handles the run_agentcore_task MCP tool execution."""
    prompt = args.get("prompt", "")
    if not isinstance(prompt, str) or not prompt.strip():
        return {"error": "A non-empty prompt is required."}
    repo = args.get("repository", ".")
    budget = float(args.get("budget", 5.0))
    mode_str = args.get("execution_mode", "AUTO").upper()
    provider = args.get("provider", "multi")
    files = args.get("files", [])

    mode_map = {
        "AUTO": ExecutionMode.AUTO,
        "FULL": ExecutionMode.FULL,
        "CREDIT_SAFE": ExecutionMode.CREDIT_SAFE,
    }
    mode = mode_map.get(mode_str, ExecutionMode.AUTO)

    import uuid
    task_id = f"mcp_{uuid.uuid4().hex[:8]}"

    executor = FakeExecutor() if provider == "fake" else MultiProviderExecutor()
    engine = AgentCoreEngine(executor=executor, repo_root=repo)

    task_input = TaskInput(
        task_id=task_id,
        prompt=prompt,
        repository=repo,
        files=files,
        budget=budget,
        budget_unit="USD",
        execution_mode=mode,
    )

    manifest = engine.initialize_task(task_input)
    manifest.orchestration["source"] = "mcp"
    if engine.current_context:
        engine.current_context.orchestration["source"] = "mcp"
    engine.checkpoint_manager.save_checkpoint(manifest)
    report = engine.run_to_completion()
    budget = budget_view(engine.current_manifest)

    return {
        "task_id": task_id,
        "status": engine.current_manifest.status,
        "report": report,
        "work_units_completed": len(engine.current_manifest.completed_work),
        "total_work_units": len(engine.work_units),
        "budget_spent_usd": float(budget.get("used", 0)),
        "budget_remaining_usd": float(budget.get("remaining", 0)),
        "budget_state": engine.current_manifest.budget_info.get("state", "NORMAL"),
        "outputs": engine.current_manifest.outputs,
        "errors": engine.current_manifest.errors,
    }


def handle_get_status(args: Dict[str, Any]) -> Dict[str, Any]:
    """Handles the get_agentcore_status MCP tool execution."""
    task_id = args.get("task_id", "")
    mgr = CheckpointManager(".agentcore/checkpoints")
    manifest = mgr.load_checkpoint(task_id)

    if not manifest:
        return {"error": f"Task checkpoint '{task_id}' not found."}

    return {
        "task_id": manifest.task_id,
        "status": manifest.status,
        "completed_units": manifest.completed_work,
        "outputs": manifest.outputs,
        "budget_info": manifest.budget_info,
        "errors": manifest.errors,
        "updated_at": getattr(manifest, "updated_at", getattr(manifest, "created_at", "")),
    }


def handle_list_checkpoints(args: Dict[str, Any]) -> Dict[str, Any]:
    """Handles listing all checkpoints."""
    import os
    checkpoint_dir = ".agentcore/checkpoints"
    results = []
    if os.path.exists(checkpoint_dir):
        for fname in os.listdir(checkpoint_dir):
            if fname.endswith("_manifest.json"):
                fpath = os.path.join(checkpoint_dir, fname)
                try:
                    m = TaskManifest.load(fpath)
                    results.append(task_summary(m, active_in_memory=False))
                except Exception:
                    continue
    results.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
    return {"checkpoints": results}


def process_mcp_request(request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Processes a JSON-RPC 2.0 MCP protocol message."""
    method = request.get("method")
    req_id = request.get("id")

    # MCP clients send this JSON-RPC notification after initialize. A
    # notification has no id and therefore must not receive a response.
    if method == "notifications/initialized":
        return None

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": MCP_TOOLS},
        }

    elif method == "tools/call":
        params = request.get("params", {})
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name == "run_agentcore_task":
            res = handle_run_task(arguments)
        elif tool_name == "get_agentcore_status":
            res = handle_get_status(arguments)
        elif tool_name == "list_agentcore_checkpoints":
            res = handle_list_checkpoints(arguments)
        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method/Tool '{tool_name}' not found"},
            }

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [{"type": "text", "text": json.dumps(res, indent=2, ensure_ascii=False)}]
            },
        }

    elif method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "agentcore-mcp-server", "version": "3.0.0"},
            },
        }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Unhandled method: {method}"},
    }


def run_stdio_server():
    """Runs the MCP server over standard input/output (stdio)."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = process_mcp_request(req)
            if resp is not None:
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()
        except Exception as e:
            err_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {str(e)}"},
            }
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()
