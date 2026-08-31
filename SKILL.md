---
name: agentcore
description: Provider-agnostic, budget-aware, resumable execution for local projects and supplied artifacts.
---

# AgentCore operating guide

Use AgentCore to produce bounded, evidenced work. Inspect current artifacts first, divide the outcome into P0–P4 work units, choose deterministic tooling before a model, then select a model by capability before price.

- Preserve the default 15% reserve and checkpoint meaningful completed work.
- Label costs as provider-confirmed, estimated, or unknown; never present fake-executor output as billing.
- Validate the artifact in its real form and report completed, skipped, blocked, and unverified work separately.
- Treat the three public policy roles as `adaptive-omni-agent`, `code-engineer`, and `credit-safe-agent`. `adaptive-omni-agent` includes internal, fallible local recall; current workspace evidence always wins.
- Real provider work requires an `OperationExecutor`; AgentCore ships no provider SDK integration.

## Local dashboard visibility

When this skill performs a non-trivial task in this workspace, create a small
non-sensitive dashboard record before work begins. This makes the work visible
at the local AgentCore website without needing any OpenAI, Anthropic, or Gemini
API key. This lifecycle is **automatic from the user's point of view**: the
agent runs the commands below itself and keeps the returned task ID in its own
working context. Never ask a user to remember, copy, or type a task ID.

```powershell
python -m src.cli skill start --title "Short Mongolian description"
```

Keep the printed `TASK_ID` internally. Update it at a meaningful checkpoint,
then finish or fail it when the task ends. Do not put a full user prompt,
credentials, tokens, keys, or private file contents into a title, message, or
summary. Do not present these commands as a user setup step; they are part of
the skill's own operating procedure.

```powershell
python -m src.cli skill update TASK_ID --message "Шалгаж байна"
python -m src.cli skill finish TASK_ID --summary "Тест амжилттай дууссан"
# Or, if work cannot continue:
python -m src.cli skill fail TASK_ID --message "Шаардлагатай файл олдсонгүй"
```

This is a local display record, not a provider connection or billing record.

See [README.md](README.md) for setup, [AGENTS.md](AGENTS.md) for repository conventions, and [references](references/) for the implementation-aligned policies.
