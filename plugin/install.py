"""AgentCore cross-agent plugin installer.

Installs AgentCore skills + slash commands into any supported AI agent
(OpenCode, Claude Code, Codex, Cursor, Windsurf, Gemini CLI), modeled on
mattpocock/skills. Runs a SkillScanner gate (agent-scan / SkillSpector
style) on the canonical `skills/` tree before installing.

Usage:
    python plugin/install.py --list
    python plugin/install.py --agents opencode,claude --scope project
    python plugin/install.py --agents codex --scope user
    python plugin/install.py --scan-only
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PLUGIN_DIR))

from agents import (  # noqa: E402
    DEFAULT_COMMANDS,
    DEFAULT_SKILLS,
    AgentTarget,
    resolve_targets,
    write_command,
    write_skill,
)
from scanner import SkillScanner  # noqa: E402


def _canonical_skills_root() -> Path:
    return PROJECT_ROOT / "skills"


def scan_canonical_skills() -> object:
    """Scan the canonical skills tree. Returns a ScanReport."""
    target = _canonical_skills_root()
    if not target.exists():
        return None
    return SkillScanner(str(target)).scan()


def install_to_target(target: AgentTarget, skills: List[str], commands: List[str]) -> List[str]:
    """Install selected skills + commands into one agent target."""
    written: List[str] = []
    for name in skills:
        if name not in DEFAULT_SKILLS:
            continue
        path = write_skill(name, DEFAULT_SKILLS[name], target)
        written.append(str(path))
    for name in commands:
        if name not in DEFAULT_COMMANDS:
            continue
        path = write_command(name, DEFAULT_COMMANDS[name], target)
        if path:
            written.append(str(path))
    return written


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="agentcore-plugin", description="Install AgentCore skills and slash commands into AI agents.")
    parser.add_argument("--list", action="store_true", help="List detected agents and install targets")
    parser.add_argument("--agents", help="Comma-separated agent names (default: all detected)")
    parser.add_argument("--scope", choices=["project", "user"], default="project", help="Install scope (default: project)")
    parser.add_argument("--skills", help="Comma-separated skill names (default: all)")
    parser.add_argument("--commands", help="Comma-separated command names (default: all)")
    parser.add_argument("--scan-only", action="store_true", help="Only scan the canonical skills tree, do not install")
    parser.add_argument("--scan-json", help="Write scan report to this file")
    parser.add_argument("--skip-scan", action="store_true", help="Do not run the security scan gate")
    parser.add_argument("--force", action="store_true", help="Install even if the scan recommends DO_NOT_INSTALL")
    args = parser.parse_args(argv)

    root = PROJECT_ROOT

    # --list -----------------------------------------------------------------
    if args.list:
        targets = resolve_targets(project_root=root, scope=args.scope)
        print(f"AgentCore cross-agent plugin")
        print(f"Project root : {root}")
        print(f"Scope        : {args.scope}")
        print()
        for t in targets:
            status = "INSTALLED" if t.installed else "not-installed"
            marker = "*" if t.exists() else " "
            print(f" {marker} {t.name:<10} cli={status:<14} skills={t.skills_dir}")
            if t.commands_dir:
                print(f"   {'':10} commands     = {t.commands_dir}")
        print()
        print("Usage: python plugin/install.py --agents <name> --scope <project|user>")
        return 0

    # --scan-only -------------------------------------------------------------
    if args.scan_only:
        report = scan_canonical_skills()
        if report is None:
            print(f"error: canonical skills root not found: {_canonical_skills_root()}", file=sys.stderr)
            return 2
        if args.scan_json:
            Path(args.scan_json).write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
            print(f"Scan report written to {args.scan_json}")
        else:
            from scanner import _format_terminal
            print(_format_terminal(report))
        return 0 if report.recommendation != "DO_NOT_INSTALL" else 1

    # --scan gate -------------------------------------------------------------
    if not args.skip_scan:
        report = scan_canonical_skills()
        if report is None:
            print(f"warning: canonical skills root not found, skipping scan gate: {_canonical_skills_root()}", file=sys.stderr)
        elif report.recommendation == "DO_NOT_INSTALL" and not args.force:
            print(f"[scan gate] ABORT: skills scan recommends DO_NOT_INSTALL (score {report.score}).", file=sys.stderr)
            print(f"[scan gate] Run with --force to override, or fix the skill and rescan.", file=sys.stderr)
            print(f"[scan gate] Report: {_format_scan_short(report)}", file=sys.stderr)
            return 1

    # --resolve agents ---------------------------------------------------------
    agents = [a.strip() for a in args.agents.split(",") if a.strip()] if args.agents else None
    targets = resolve_targets(project_root=root, scope=args.scope, agents=agents)
    targets = [t for t in targets if not args.agents] or targets
    if not targets:
        print("error: no agents selected", file=sys.stderr)
        return 2

    skills = [s.strip() for s in args.skills.split(",") if s.strip()] if args.skills else list(DEFAULT_SKILLS.keys())
    commands = [c.strip() for c in args.commands.split(",") if c.strip()] if args.commands else list(DEFAULT_COMMANDS.keys())

    total = 0
    for t in targets:
        written = install_to_target(t, skills, commands)
        total += len(written)
        print(f"[{t.name}:{t.scope}] installed {len(written)} files -> {t.skills_dir.parent}")
        for w in written:
            print(f"    {w}")

    print(f"\nInstalled {total} files across {len(targets)} agent target(s).")
    if not any(t.installed for t in targets):
        print("Note: no matching agent CLI was found on PATH; files were still written to disk.")
    return 0


def _format_scan_short(report) -> str:
    return f"score={report.score} severity={report.severity} findings={len(report.findings)}"


if __name__ == "__main__":
    raise SystemExit(main())