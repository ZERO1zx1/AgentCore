# AgentCore contributor guide

Provider-agnostic, budget-aware execution engine. Read `README.md` plus `references/` before changing a pipeline boundary (`InputRouter` → `Planner`/`Scheduler` → `ModelRouter` → `OperationExecutor`, with `BudgetManager` gating). Entry point is `AgentCoreEngine` in `src/core/engine.py`; CLI is `python -m src.cli` (`run`, `list`, `resume`, `mcp`, `skill`, `observe`).

## Setup and validation

Requires Python 3.10+ (CI uses 3.11):

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests/test_<name>.py -v   # focused check first
python -m pytest tests -v                   # engine suite
python -m compileall src plugin feat examples/backend
```

Cross-cutting changes also need (mirrors `.github/workflows/test.yml`):

```bash
python -m pytest feat/low_cost_skill/tests -v
python -W error::ResourceWarning -m pytest plugin/ -v
python -m unittest skills/adaptive-local-memory/scripts/test_memory.py -v
```

`examples/backend/express` has its own locked suite (`npm ci`, `npm test`, `npm audit --audit-level=high`). `feat/low_cost_skill/` is a separate POC, not engine wiring — never import it from `src/`.

## Rules

- Use `AgentCore` / `AgentCoreEngine`; "Manus Mini" is legacy runtime data only.
- Keep provider adapters external: `FakeExecutor` and `fake-*` models are offline demos, never billing. Real execution needs your own `OperationExecutor`; register accurate `ModelSpec` values in an injected registry.
- Money is `Decimal`-only, always via `Decimal(str(x))` (never float math). Preserve the default 15% reserve (`reserve_ratio=0.15` in `src/checkpoint/manifest.py`, `src/budget/state.py`).
- `TaskManifest` schema is 3.0; checkpoint/resume lives in `.agentcore/checkpoints/` via `CheckpointManager`. Resume with `python -m src.cli resume <task_id>`.
- Budget-recovery git (`src/core/notifications.py:GitManager`) stages only the explicit checkpoint file (`git add -- <relative>`). Never `git add -A`, never auto-commit unrelated work, never commit secrets. `.agentcore/`, `*.db`, `node_modules/` are gitignored runtime output — CI enforces `git check-ignore` policy for them but `package-lock.json` must stay trackable.
- Media arrives as verified path descriptors in `context["attachments"]` (path, MIME, size, SHA-256). Adapters convert to provider format; never inline binary/base64 into prompts.
- `pypdf` missing means a PDF task persists as `BLOCKED` with `DEPENDENCY_UNAVAILABLE` — never return placeholder extraction.
- `src/memory` lessons are fallible local recall; current workspace evidence always wins.
- Docs must describe implemented behavior, not planned integrations.

## Navigation

- `README.md`: setup, architecture, adapter boundary.
- `src/README.md`, `src/cli/README.md`, `tests/README.md`, `skills/README.md`, `feat/README.md`: package ownership.
- `references/`: budget, checkpointing, model-routing, output-contract semantics.
- `docs/PROJECT_GUIDE.md`: Mongolian quick-start summary (README/AGENTS/SKILL merged).
- `docs/CREDIT-MANAGEMENT.md`: optional application-integration draft.
