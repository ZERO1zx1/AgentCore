"""Command Line Interface (CLI) for AgentCore.
Provides commands for running tasks and managing checkpoints.
"""

import sys
import argparse
import os
import json
import subprocess
from pathlib import Path

from src.core.engine import AgentCoreEngine
from src.core.task import TaskInput
from src.core.modes import ExecutionMode
from src.core.executor import FakeExecutor
from src.checkpoint.manager import CheckpointManager
from src.checkpoint.manifest import TaskManifest
from src.observability.manifest_view import budget_view, manifest_prompt, manifest_timestamp
from src.core.planner import WorkUnit


def main():
    parser = argparse.ArgumentParser(
        prog="agentcore",
        description="AgentCore: Provider-Agnostic, Budget-Aware AI Agent Execution Engine CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: run
    run_parser = subparsers.add_parser("run", help="Run an autonomous task")
    run_parser.add_argument("--prompt", "-p", required=True, help="Task goal or prompt")
    run_parser.add_argument("--task-id", "-t", default=None, help="Optional unique task ID")
    run_parser.add_argument("--repo", "-r", default=".", help="Repository root directory")
    run_parser.add_argument("--budget", "-b", type=float, default=5.0, help="Budget in USD (default: 5.0)")
    run_parser.add_argument("--mode", "-m", default="AUTO", choices=["AUTO", "FULL", "CREDIT_SAFE"], help="Execution mode")
    run_parser.add_argument("--provider", default="fake", choices=["multi", "fake", "ollama"], help="Executor provider backend")
    run_parser.add_argument("--files", "-f", nargs="*", default=[], help="File paths for attachments or documents")

    # Command: list
    list_parser = subparsers.add_parser("list", help="List all saved task checkpoints")

    # Command: resume
    resume_parser = subparsers.add_parser("resume", help="Resume a task from checkpoint")
    resume_parser.add_argument("task_id", help="Task ID to resume")
    resume_parser.add_argument("--provider", default="fake", choices=["multi", "fake", "ollama"], help="Executor provider backend")

    # Command: mcp
    mcp_parser = subparsers.add_parser("mcp", help="Run Model Context Protocol (MCP) Server over stdio")

    # Command: observe
    observe_parser = subparsers.add_parser(
        "observe",
        help="Run a terminal command and record its progress as a checkpoint",
    )
    observe_parser.add_argument("--title", required=True, help="Short Mongolian description recorded for the task")
    observe_parser.add_argument("--repo", "-r", default=".", help="Working directory for the command")
    observe_parser.add_argument("terminal_command", nargs=argparse.REMAINDER, help="Command after --, for example: -- python -m pytest")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if args.command == "mcp":
        from src.mcp.server import run_stdio_server
        run_stdio_server()

    elif args.command == "observe":
        command = list(args.terminal_command)
        if command[:1] == ["--"]:
            command = command[1:]
        if not command:
            parser.error("observe requires a command after --")

        task_id = f"terminal_{os.urandom(4).hex()}"
        checkpoint_mgr = CheckpointManager(".agentcore/checkpoints")
        manifest = TaskManifest(
            task_id=task_id,
            input_type="terminal",
            sources=[],
            initial_budget=0,
            budget_unit="LOCAL",
            execution_mode="OBSERVE_ONLY",
        )
        unit = WorkUnit(
            id="terminal_command",
            type="terminal",
            priority="P0",
            instruction=args.title,
            required_capabilities=[],
            status="in_progress",
        )
        manifest.work_units_data = [unit.to_dict()]
        manifest.progress = {"completed_units": 0, "total_units": 1, "current_unit": unit.id}
        manifest.task_context_dict = {
            "task_id": task_id,
            "user_prompt": args.title,
            "execution_mode": "OBSERVE_ONLY",
            "requested_output_type": "terminal",
            "input_sources": [],
            "metadata": {"working_directory": os.path.abspath(args.repo)},
            "orchestration": {"source": "terminal", "control": "observe_only"},
            "memory_hits": [],
        }
        manifest.orchestration = {"source": "terminal", "control": "observe_only"}
        checkpoint_mgr.save_checkpoint(manifest)

        artifact_dir = Path(".agentcore") / "tasks" / task_id / "artifacts"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        log_path = artifact_dir / "terminal-output.txt"
        print(f"AgentCore ажил бүртгэгдлээ: {args.title}")
        print(f"Task ID: {task_id}")

        try:
            with log_path.open("w", encoding="utf-8", errors="replace") as log_file:
                process = subprocess.Popen(
                    command,
                    cwd=args.repo,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                assert process.stdout is not None
                for line in process.stdout:
                    print(line, end="")
                    log_file.write(line)
                exit_code = process.wait()
        except OSError as exc:
            exit_code = -1
            with log_path.open("w", encoding="utf-8") as log_file:
                log_file.write(f"Could not start command: {exc}\n")

        unit.status = "completed" if exit_code == 0 else "failed"
        manifest.work_units_data = [unit.to_dict()]
        manifest.progress = {"completed_units": 1 if exit_code == 0 else 0, "total_units": 1, "current_unit": unit.id}
        manifest.outputs = [str(log_path.resolve())]
        if exit_code == 0:
            manifest.set_status("COMPLETED")
            print("Ажил дууслаа.")
        else:
            manifest.set_status("FAILED")
            manifest.errors.append(f"Terminal command exited with code {exit_code}.")
            print(f"Ажил алдаатай дууслаа (code {exit_code}). Log хадгалагдсан.")
        checkpoint_mgr.save_checkpoint(manifest)

    elif args.command == "run":
        # Provider adapters are optional for local/offline commands. Import the
        # HTTP-backed adapter only when a provider-backed execution is requested,
        # so local commands can run in a minimal runtime.
        mode_map = {
            "AUTO": ExecutionMode.AUTO,
            "FULL": ExecutionMode.FULL,
            "CREDIT_SAFE": ExecutionMode.CREDIT_SAFE,
        }
        mode = mode_map.get(args.mode, ExecutionMode.AUTO)

        if args.provider == "fake":
            executor = FakeExecutor()
        else:
            from src.adapters.provider import MultiProviderExecutor

            executor = MultiProviderExecutor()

        engine = AgentCoreEngine(executor=executor, repo_root=args.repo)

        task_id = args.task_id or f"cli_{os.urandom(4).hex()}"
        task_input = TaskInput(
            task_id=task_id,
            prompt=args.prompt,
            repository=args.repo,
            files=args.files,
            budget=args.budget,
            budget_unit="USD",
            execution_mode=mode,
        )

        print(f"\n========================================================")
        print(f"🚀 Initializing AgentCore Task: {task_id}")
        print(f"🎯 Goal: {args.prompt}")
        print(f"💰 Budget: ${args.budget:.2f} USD | Mode: {args.mode}")
        print(f"========================================================\n")

        manifest = engine.initialize_task(task_input)
        manifest.orchestration["source"] = "cli"
        if engine.current_context:
            engine.current_context.orchestration["source"] = "cli"
        engine.checkpoint_manager.save_checkpoint(manifest)
        print(f"📋 Generated {len(engine.work_units)} WorkUnits in execution DAG:")
        for idx, unit in enumerate(engine.work_units, 1):
            desc = unit.instruction or unit.id
            print(f"   [{unit.priority}] #{idx} {unit.id} ({unit.type}): {desc}")

        print(f"\n⚡ Executing task to completion...\n")
        report = engine.run_to_completion()

        print(f"\n========================================================")
        print(f"✅ Execution Finished! Status: {engine.current_manifest.status.upper()}")
        print(f"💰 Final Budget State: {engine.current_manifest.budget_info.get('state', 'UNKNOWN')}")
        print(f"📁 Output Artifacts ({len(engine.current_manifest.outputs)}):")
        for out in engine.current_manifest.outputs:
            print(f"   - {out}")
        print(f"========================================================\n")

    elif args.command == "list":
        checkpoint_dir = ".agentcore/checkpoints"
        if os.path.exists(checkpoint_dir):
            files = [os.path.join(checkpoint_dir, f) for f in os.listdir(checkpoint_dir) if f.endswith("_manifest.json")]
            print(f"\n📋 Found {len(files)} Saved Checkpoint(s):")
            for path in files:
                try:
                    m = TaskManifest.load(path)
                    print(f"   - [{m.status.upper()}] Task: {m.task_id} | Completed: {len(m.completed_work)} units | {manifest_timestamp(m)}")
                except Exception:
                    print(f"   - Task file: {os.path.basename(path)}")
            print("")
        else:
            print("\n📋 No checkpoints directory found.\n")

    elif args.command == "resume":
        mgr = CheckpointManager(".agentcore/checkpoints")
        manifest = mgr.load_checkpoint(args.task_id)
        if not manifest:
            print(f"❌ Error: Checkpoint for task '{args.task_id}' not found.")
            sys.exit(1)

        if args.provider == "fake":
            executor = FakeExecutor()
        else:
            from src.adapters.provider import MultiProviderExecutor

            executor = MultiProviderExecutor()
        engine = AgentCoreEngine(executor=executor)

        task_input = TaskInput(
            task_id=args.task_id,
            prompt=manifest_prompt(manifest),
            resume_task_id=args.task_id,
        )

        print(f"\n🔄 Resuming Task '{args.task_id}' from checkpoint...")
        engine.initialize_task(task_input)
        report = engine.run_to_completion()
        print(f"✅ Resumed task finished with status: {engine.current_manifest.status}\n")


if __name__ == "__main__":
    main()
