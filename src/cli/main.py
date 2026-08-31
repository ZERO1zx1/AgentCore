"""Command Line Interface (CLI) for AgentCore.
Provides commands for running tasks, serving the Web Dashboard, and managing checkpoints.
"""

import sys
import argparse
import os
import json
import subprocess
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

from src.core.engine import AgentCoreEngine
from src.core.task import TaskInput
from src.core.modes import ExecutionMode
from src.core.executor import FakeExecutor
from src.adapters.provider import MultiProviderExecutor
from src.checkpoint.manager import CheckpointManager
from src.checkpoint.manifest import TaskManifest
from src.observability.manifest_view import budget_view, manifest_prompt, manifest_timestamp
from src.core.planner import WorkUnit


DASHBOARD_URL = "http://127.0.0.1:8000"


def _dashboard_is_available() -> bool:
    """Return whether the local dashboard is already accepting requests."""
    try:
        with urllib.request.urlopen(f"{DASHBOARD_URL}/api/health", timeout=0.4) as response:
            return 200 <= response.status < 300
    except (OSError, ValueError):
        return False


def _open_dashboard_when_ready() -> None:
    """Wait briefly for a local server, then open the normal browser once."""
    def wait_and_open() -> None:
        for _ in range(20):
            if _dashboard_is_available():
                webbrowser.open(DASHBOARD_URL, new=2)
                return
            time.sleep(0.2)
        # Opening still gives the user a useful browser page if server startup
        # failed; the URL stays local and has no external side effect.
        webbrowser.open(DASHBOARD_URL, new=2)

    threading.Thread(target=wait_and_open, daemon=True).start()


def _ensure_dashboard_is_open() -> None:
    """Start the local-only dashboard when needed and open it for the user."""
    if not _dashboard_is_available():
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        subprocess.Popen(
            [sys.executable, "-m", "src.cli", "serve", "--no-browser"],
            cwd=os.getcwd(),
            creationflags=creation_flags,
        )
    _open_dashboard_when_ready()


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

    # Command: serve
    serve_parser = subparsers.add_parser("serve", help="Launch AgentCore Web Dashboard")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host address (default: 127.0.0.1)")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port number (default: 8000)")
    serve_parser.add_argument("--reload", action="store_true", help="Auto-reload on changes")
    serve_parser.add_argument("--no-browser", action="store_true", help="Do not open the local dashboard in a browser")

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
        help="Run a terminal command and show its progress in the local dashboard",
    )
    observe_parser.add_argument("--title", required=True, help="Short Mongolian description shown in the dashboard")
    observe_parser.add_argument("--repo", "-r", default=".", help="Working directory for the command")
    observe_parser.add_argument("terminal_command", nargs=argparse.REMAINDER, help="Command after --, for example: -- python -m pytest")

    # Command: skill
    # This small bridge lets a Codex/AgentCore skill expose its own work in the
    # local dashboard without requiring a provider API key or a cloud service.
    skill_parser = subparsers.add_parser(
        "skill",
        help="Show AgentCore skill work in the local dashboard",
    )
    skill_actions = skill_parser.add_subparsers(dest="skill_action", required=True)
    skill_start = skill_actions.add_parser("start", help="Create a dashboard record for skill work")
    skill_start.add_argument("--title", required=True, help="Short, non-sensitive description shown in the dashboard")
    skill_start.add_argument("--task-id", default=None, help="Optional dashboard task ID")
    skill_start.add_argument("--no-open-dashboard", action="store_true", help="Do not automatically start or open the local dashboard")
    skill_update = skill_actions.add_parser("update", help="Update the visible skill-work message")
    skill_update.add_argument("task_id", help="Task ID printed by skill start")
    skill_update.add_argument("--message", required=True, help="Short, non-sensitive progress message")
    skill_finish = skill_actions.add_parser("finish", help="Mark visible skill work complete")
    skill_finish.add_argument("task_id", help="Task ID printed by skill start")
    skill_finish.add_argument("--summary", required=True, help="Short, non-sensitive completion summary")
    skill_fail = skill_actions.add_parser("fail", help="Mark visible skill work as blocked or failed")
    skill_fail.add_argument("task_id", help="Task ID printed by skill start")
    skill_fail.add_argument("--message", required=True, help="Short, non-sensitive failure message")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if args.command == "mcp":
        from src.mcp.server import run_stdio_server
        run_stdio_server()

    elif args.command == "skill":
        checkpoint_mgr = CheckpointManager(".agentcore/checkpoints")

        if args.skill_action == "start":
            task_id = args.task_id or f"skill_{os.urandom(4).hex()}"
            manifest = TaskManifest(
                task_id=task_id,
                input_type="agentcore_skill",
                sources=[],
                initial_budget=0,
                budget_unit="LOCAL",
                execution_mode="OBSERVE_ONLY",
            )
            unit = WorkUnit(
                id="agentcore_skill_work",
                type="analyze",
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
                "requested_output_type": "skill_work",
                "input_sources": [],
                "metadata": {},
                "orchestration": {"source": "agentcore_skill", "control": "dashboard_bridge"},
                "memory_hits": [],
            }
            manifest.orchestration = {"source": "agentcore_skill", "control": "dashboard_bridge"}
            checkpoint_mgr.save_checkpoint(manifest)
            if not args.no_open_dashboard:
                _ensure_dashboard_is_open()
            print(f"TASK_ID={task_id}")
            print("AgentCore skill-ийн ажил website дээр харагдаж эхэллээ.")

        else:
            manifest = checkpoint_mgr.load_checkpoint(args.task_id)
            if not manifest:
                print(f"Task '{args.task_id}' олдсонгүй.")
                sys.exit(1)
            if manifest.orchestration.get("source") != "agentcore_skill":
                print("Энэ task нь AgentCore skill dashboard record биш байна.")
                sys.exit(1)

            units = [WorkUnit.from_dict(item) for item in manifest.work_units_data]
            if not units:
                print("Skill task-ийн ажиллах нэгж олдсонгүй.")
                sys.exit(1)
            unit = units[0]

            if args.skill_action == "update":
                unit.instruction = args.message
                unit.status = "in_progress"
                manifest.work_units_data = [unit.to_dict()]
                manifest.progress = {"completed_units": 0, "total_units": 1, "current_unit": unit.id}
                manifest.set_status("IN_PROGRESS")
                print("Website дээрх ажлын мэдээлэл шинэчлэгдлээ.")
            elif args.skill_action == "finish":
                unit.instruction = args.summary
                unit.status = "completed"
                manifest.work_units_data = [unit.to_dict()]
                manifest.progress = {"completed_units": 1, "total_units": 1, "current_unit": unit.id}
                manifest.set_status("COMPLETED")
                print("AgentCore skill-ийн ажил website дээр дууссан гэж тэмдэглэгдлээ.")
            else:  # fail
                unit.instruction = args.message
                unit.status = "failed"
                manifest.work_units_data = [unit.to_dict()]
                manifest.progress = {"completed_units": 0, "total_units": 1, "current_unit": unit.id}
                manifest.errors.append(args.message)
                manifest.set_status("FAILED")
                print("AgentCore skill-ийн ажил website дээр алдаатай гэж тэмдэглэгдлээ.")

            checkpoint_mgr.save_checkpoint(manifest)

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
        print(f"AgentCore website дээр харагдаж эхэллээ: {args.title}")
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
            print("Ажил дууслаа. Үр дүнг website дээрээс нээж болно.")
        else:
            manifest.set_status("FAILED")
            manifest.errors.append(f"Terminal command exited with code {exit_code}.")
            print(f"Ажил алдаатай дууслаа (code {exit_code}). Log website дээр хадгалагдсан.")
        checkpoint_mgr.save_checkpoint(manifest)

    elif args.command == "serve":
        import uvicorn
        print(f"\n🚀 Starting AgentCore Web Dashboard at http://{args.host}:{args.port}")
        print(f"📊 Control center, live DAG visualizer, and budget monitors are active.\n")
        if not args.no_browser and args.host in {"127.0.0.1", "localhost"}:
            _open_dashboard_when_ready()
        uvicorn.run("src.server.app:app", host=args.host, port=args.port, reload=args.reload)

    elif args.command == "run":
        mode_map = {
            "AUTO": ExecutionMode.AUTO,
            "FULL": ExecutionMode.FULL,
            "CREDIT_SAFE": ExecutionMode.CREDIT_SAFE,
        }
        mode = mode_map.get(args.mode, ExecutionMode.AUTO)

        if args.provider == "fake":
            executor = FakeExecutor()
        else:
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

        executor = FakeExecutor() if args.provider == "fake" else MultiProviderExecutor()
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
