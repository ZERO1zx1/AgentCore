"""Agent registry for AgentCore cross-agent plugin.

Maps each supported AI agent (OpenCode, Claude Code, Codex, Cursor,
Windsurf, Gemini CLI) to its skills directory, slash-command directory,
and frontmatter/format conventions. Inspired by mattpocock/skills.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

# Executable names used to detect whether an agent CLI is installed.
AGENT_EXECUTABLES: Dict[str, List[str]] = {
    "opencode": ["opencode"],
    "claude": ["claude"],
    "codex": ["codex"],
    "cursor": ["cursor"],
    "windsurf": ["windsurf"],
    "gemini": ["gemini"],
}

# Per-agent, per-scope (project/user) skill + command directories.
# `home` markers are resolved against the user home directory.
AGENT_LAYOUTS: Dict[str, Dict[str, dict]] = {
    "opencode": {
        "project": {
            "skills": ".opencode/skills",
            "commands": ".opencode/commands",
        },
        "user": {
            "skills": "~/.config/opencode/skills",
            "commands": "~/.config/opencode/commands",
        },
    },
    "claude": {
        "project": {
            "skills": ".claude/skills",
            "commands": ".claude/commands",
        },
        "user": {
            "skills": "~/.claude/skills",
            "commands": "~/.claude/commands",
        },
    },
    "codex": {
        "project": {
            "skills": ".agents/skills",
            "commands": ".agents/commands",
        },
        "user": {
            "skills": "~/.codex/skills",
            "commands": "~/.codex/commands",
        },
    },
    "cursor": {
        "project": {
            "skills": ".cursor/skills",
            "commands": ".cursor/commands",
        },
        "user": {
            "skills": "~/.cursor/skills",
            "commands": "~/.cursor/commands",
        },
    },
    "windsurf": {
        "project": {
            "skills": ".windsurf/skills",
            "commands": ".windsurf/commands",
        },
        "user": {
            "skills": "~/.windsurf/skills",
            "commands": "~/.windsurf/commands",
        },
    },
    "gemini": {
        "project": {
            "skills": ".gemini/skills",
            "commands": ".gemini/commands",
        },
        "user": {
            "skills": "~/.gemini/skills",
            "commands": "~/.gemini/commands",
        },
    },
}

# Skills shipped by this plugin (name -> SKILL.md body). The bodies are
# short, self-contained prompts (mattpocock-style) so they work in any agent.
DEFAULT_SKILLS: Dict[str, str] = {
    "adaptive-omni-agent": """---
name: adaptive-omni-agent
description: Turn any prompt into bounded artifact-aware, model-adaptive, budget-safe, verified work across code, apps, infrastructure, data, documents, and media.
---

# Adaptive Omni Agent

Orchestrate intent, artifact, and capability routing for the given request.
Then delegate to the appropriate specialist skill.

## Steps

1. Classify intent: code, app/infra, data, document, media.
2. Determine artifact types and required capabilities.
3. Route to `code-engineer` and/or `credit-safe-agent` as appropriate.
4. Recall a small number of relevant local lessons; treat them as fallible hints and let current workspace evidence win.
5. Deliver a verified result with explicit evidence of validation. Record only verified, reusable lessons without secrets or personal data.
""",
    "code-engineer": """---
name: code-engineer
description: Inspect, build, fix, transform, and validate heterogeneous code, infrastructure, data, document, slide, image, audio, and video projects using artifact-appropriate tools.
---

# Code Engineer

Autonomous senior software engineering.

## Steps

1. Inspect repository structure and trace data flow before editing.
2. Implement minimal complete changes following existing conventions.
3. Validate with real commands (tests, lint, typecheck, compile).
4. Review diffs and verify no unrelated changes or secrets.
""",
    "credit-safe-agent": """---
name: credit-safe-agent
description: Run broad and experimental work while enforcing token, credit, time, dollar, reserve, checkpoint, and resumability constraints.
---

# Credit Safe Agent

Budget-first autonomous execution.

## Steps

1. Plan work as P0-P4 priority units.
2. Keep an emergency reserve and never spend it on optional work.
3. Checkpoint progress incrementally so work is resumable.
4. On exhaustion, persist state and stop gracefully.
""",
}

# Slash commands shipped by this plugin. name -> frontmatter + body.
# `{agentcore_root}` is the absolute path of the AgentCore repository.
DEFAULT_COMMANDS: Dict[str, str] = {
    "agentcore": """---
name: agentcore
description: Load AgentCore project context, show status, and identify relevant skills
---

Load AGENTS.md for AgentCore instructions, then show repository state, current task/checkpoint, budget state, and the three-policy route.
""",
    "adaptive-omni": """---
name: adaptive-omni
description: Run any request through the AgentCore adaptive orchestrator (code + credit-safe + memory)
---

Use the `adaptive-omni-agent` skill to run the given request through intent/artifact/capability routing with budget safety.
""",
    "code-engineer": """---
name: code-engineer
description: Run artifact-aware implementation or diagnosis with credit control
---

Use the `code-engineer` skill for implementation, debugging, refactoring, testing, validation, or architecture review, with credit control.
""",
    "credit-safe": """---
name: credit-safe
description: Run budget-first work with reserve and checkpoint protection
---

Use the `credit-safe-agent` skill to enforce budget, checkpoint, and resumability constraints.
""",
    "status": """---
name: status
description: Show repository, task, checkpoint, and budget state
---

Show AgentCore repo state (branch, tree), active task, latest checkpoint, and budget status.
""",
    "resume": """---
name: resume
description: Resume from the last AgentCore checkpoint (inspects real persisted state)
---

Inspect `.agentcore/checkpoints/` for the most recent task manifest and resume it.
""",
    "checkpoint": """---
name: checkpoint
description: Trigger a manual AgentCore checkpoint
---

Persist the current task state to `.agentcore/checkpoints/`.
""",
    "test": """---
name: test
description: Run the AgentCore validation suite
---

Run `python -m pytest tests/ -v` from the AgentCore root.
""",
}


@dataclass
class AgentTarget:
    """Resolved install location for one agent."""
    name: str
    scope: str
    skills_dir: Path
    commands_dir: Optional[Path]
    installed: bool  # CLI detected on PATH
    home: bool  # whether it targets the user home (vs project root)

    def exists(self) -> bool:
        return self.skills_dir.exists() or (self.commands_dir and self.commands_dir.exists())


def _resolve(p: str, home: Path) -> Path:
    if p.startswith("~"):
        return home / p.lstrip("~\\/")
    return Path(p)


def resolve_home() -> Path:
    return Path.home()


def resolve_targets(
    project_root: Optional[Path] = None,
    scope: str = "project",
    agents: Optional[List[str]] = None,
) -> List[AgentTarget]:
    """Resolve install targets for requested (or all) agents."""
    home = resolve_home()
    root = project_root or Path.cwd()
    agent_names = agents or list(AGENT_LAYOUTS.keys())

    targets: List[AgentTarget] = []
    for name in agent_names:
        if name not in AGENT_LAYOUTS:
            continue
        layout = AGENT_LAYOUTS[name]
        scope_cfg = layout.get(scope) or layout["project"]
        skills_dir = _resolve(scope_cfg["skills"], home)
        if scope == "project":
            skills_dir = root / scope_cfg["skills"].lstrip("~\\/")
        cmd_dir = scope_cfg.get("commands")
        commands_dir = _resolve(cmd_dir, home) if cmd_dir else None
        if scope == "project" and cmd_dir:
            commands_dir = root / cmd_dir.lstrip("~\\/")
        installed = shutil.which(AGENT_EXECUTABLES[name][0]) is not None
        targets.append(AgentTarget(
            name=name,
            scope=scope,
            skills_dir=skills_dir,
            commands_dir=commands_dir,
            installed=installed,
            home=(scope == "user"),
        ))
    return targets


def write_skill(name: str, content: str, target: AgentTarget) -> Path:
    """Install a skill into an agent target. Returns written path."""
    dest = target.skills_dir / name / "SKILL.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    return dest


def write_command(name: str, content: str, target: AgentTarget) -> Optional[Path]:
    """Install a slash command into an agent target (if supported)."""
    if not target.commands_dir:
        return None
    dest = target.commands_dir / f"{name}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    return dest
