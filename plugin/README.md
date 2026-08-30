# AgentCore Cross-Agent Plugin

> This plugin distributes AgentCore skills and commands; it does not install a provider adapter or grant a target agent authority to spend, deploy, or access credentials.

Install AgentCore skills and slash commands into any AI agent, and vet
skills for security before they go anywhere.

Inspired by:
- **mattpocock/skills** — portable, per-agent skills + slash commands
- **snyk/agent-scan** — security scanning for AI agent artifacts
- **NVIDIA/SkillSpector** — static skill vulnerability detection with risk scoring

## What's Inside

```
plugin/
├── install.py     # cross-agent installer (CLI)
├── scanner.py     # skill security scanner (SkillSpector/agent-scan style)
├── agents.py      # per-agent layout registry + write helpers
├── tests/         # pytest/unittest suite (18 tests)
└── README.md
```

## Quick Start

```bash
# List detected agents and their install targets
python plugin/install.py --list

# Install all skills + commands into OpenCode (project scope)
python plugin/install.py --agents opencode

# Install into Claude Code at user scope (home dir)
python plugin/install.py --agents claude --scope user

# Scan-only: vet the canonical skills/ tree
python plugin/install.py --scan-only

# CI-style scan with JSON report and non-zero exit on DO_NOT_INSTALL
python plugin/scanner.py skills/ -f json -o scan-report.json --ci
```

## Supported Agents

| Agent     | Skills dir                | Commands dir             |
|-----------|---------------------------|--------------------------|
| OpenCode  | `.opencode/skills`        | `.opencode/commands`     |
| Claude    | `.claude/skills`          | `.claude/commands`       |
| Codex     | `.agents/skills`          | `.agents/commands`       |
| Cursor    | `.cursor/skills`          | `.cursor/commands`       |
| Windsurf  | `.windsurf/skills`        | `.windsurf/commands`     |
| Gemini    | `.gemini/skills`          | `.gemini/commands`       |

Each agent gets these skills:

- `adaptive-omni-agent`
- `code-engineer`
- `credit-safe-agent`

`adaptive-omni-agent` includes bounded local-memory recall and verified lesson recording. It is not installed as a separate public skill.

And these slash commands:

- `/agentcore`, `/adaptive-omni`, `/code-engineer`, `/credit-safe`
- `/status`, `/resume`, `/checkpoint`, `/test`

## Security Gate

`install.py` runs a static scan over the canonical `skills/` tree before
installing (SkillSpector-style scoring, agent-scan-style checks):

- **Prompt injection / anti-refusal** — instruction override, persona
  takeover, refusal suppression
- **Exfiltration** — network calls carrying secrets/env, context leakage
- **Secrets** — hardcoded API keys, credential file access
- **Dangerous execution** — `curl | bash`, base64-exec, subprocess abuse,
  persistence/self-modification
- **Obfuscation** — encoded blobs, dynamic eval/exec, bidi Unicode

Scoring: `LOW 0-20` → SAFE, `MEDIUM 21-50` → CAUTION, `HIGH 51-80` /
`CRITICAL 81-100` → DO_NOT_INSTALL. If the gate recommends
DO_NOT_INSTALL, the installer aborts unless `--force` is passed.

## Installer Flags

```
--list           List detected agents and targets
--agents <n>     Comma-separated agent names (default: all)
--scope <s>      project | user (default: project)
--skills <n>     Comma-separated skill names (default: all)
--commands <n>   Comma-separated command names (default: all)
--scan-only      Scan only, do not install
--scan-json <f>  Write scan report JSON
--skip-scan      Skip the security gate
--force          Install even on DO_NOT_INSTALL
```

## Tests

```bash
python -m pytest plugin/tests/ -v
```
