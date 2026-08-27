# AgentCore — OpenCode Project Instructions

Provider-agnostic, budget-aware, resumable AI agent execution framework. Three coordinated roles: `adaptive-omni-agent` (intent/capability routing), `code-engineer` (artifact work), `credit-safe-agent` (budget/checkpoint control). `adaptive-local-memory` is an internal bounded evidence subsystem, not a public role.

## Architecture (data flow)

```
TaskInput → InputRouter → TaskContext
    ↓
Planner → WorkUnits (P0–P4) → Scheduler
    ↓
ExecutionPolicy → ModelRegistry → OperationExecutor
    ↓
BudgetManager (decimal-safe) → CheckpointManager
    ↓
ArtifactManager → OutputManager → Resume
```

Where things live (read the file before editing it):

| Module | Role |
|--------|------|
| `src/core/engine.py` | `AgentCoreEngine` orchestrator (entrypoint) |
| `src/core/orchestrator.py` | Three-skill routing |
| `src/core/planner.py` | `Planner`, `Scheduler`, `WorkUnit` (P0–P4) |
| `src/core/policy.py` | `ExecutionPolicy` (AUTO/FULL/CREDIT_SAFE) |
| `src/budget/state.py` | `BudgetManager`, `BudgetState` (NORMAL→EXHAUSTED) |
| `src/checkpoint/manifest.py` | `TaskManifest` V3 (skill-route persistence) |
| `src/models/registry.py` | `ModelRegistry`, `ModelSpec` (capability routing) |
| `src/core/executor.py` | `OperationExecutor` contract + `FakeExecutor` |
| `src/ingestion/router.py` | `InputRouter` (repo, PDF, text, JSON/CSV, media metadata) |
| `src/core/notifications.py` | `GitManager`, `NotificationManager` |

Execution modes: **AUTO** (default, skips P3/P4 at CRITICAL+), **FULL** (quality, skips only at EMERGENCY+), **CREDIT_SAFE** (cheapest-capable, aggressive skipping).

Budget states (ratio of remaining/initial): `NORMAL >0.50 → CONSERVE ≤0.50 → CRITICAL ≤0.25 → EMERGENCY ≤0.10 → EXHAUSTED ≤0`. Emergency reserve (15%) is never spent on optional work.

## Validation commands

```bash
python -m pytest tests/ -v          # runs the full core suite (CI command)
python -m unittest discover tests -v # optional stdlib-compatible runner
python -m pytest tests/test_v2_refined.py -v  # single file
python -m compileall src tests      # CI also compiles
python -c "from src.core.engine import AgentCoreEngine; print('OK')"
npm --prefix examples/frontend ci
npm --prefix examples/frontend test -- --runInBand
npm --prefix examples/frontend run build
npm --prefix examples/backend/express ci
npm --prefix examples/backend/express test
```

- **Python**: 3.11+ (CI runs on 3.11). Local dev uses 3.13.
- **Deps**: `pip install -r requirements.txt` (pypdf≥3.0.0, required). Dev/test deps: `requirements-dev.txt` (adds reportlab≥4.0 for PDF test fixtures). CI installs `requirements-dev.txt`.
- `pytest` is declared in `requirements-dev.txt`; keep tests compatible with the existing suite conventions.

## OpenCode commands & skills

Slash commands (real, in `.opencode/commands/`): `/agentcore`, `/status`, `/resume`, `/checkpoint`, `/test`.

The three roles are **skills** (in `.opencode/skills/` / `skills/`), loaded via `/skill code-engineer`, `/skill credit-safe-agent`, or `/skill adaptive-omni-agent` — they are NOT slash commands. Do not reference `/code-engineer` etc. as commands.

## Provider abstraction

- The engine only knows `prompt`, `capabilities`, `ExecutionResult`, `usage`, `artifacts`. It has **no provider SDK dependency**.
- `FakeExecutor` is the default and does **no real model calls** (test/demo only). Real execution requires implementing `OperationExecutor`.
- **Never present estimated cost as provider billing.** Keep `estimated_cost` / `charged_cost` / `actual_cost` / `cost_source` (`"provider"` verified vs `"estimate"` not) separate.
- Emergency reserve (15% of initial budget) is never spent on optional work.
- PDF processing raises a typed `RuntimeError` and persists `BLOCKED / DEPENDENCY_UNAVAILABLE` when `pypdf` is missing — it does not crash or return placeholder content.

## Checkpoint / resume

- `TaskManifest` V3 (`schema_version: "3.0"`; loads older) persisted to `.agentcore/checkpoints/{task_id}_manifest.json`.
- SHA-256 source fingerprinting drives granular, dependency-aware invalidation on resume.
- Runtime state lives in `.agentcore/` (inspectable, never hidden): `checkpoints/`, `tasks/{id}/{context,artifacts,checkpoints}/`, `git_fallback/` (failed push payloads), `notifications.log`.
- Budget-exhaustion Git staging is limited to the explicit checkpoint file; never stage unrelated work. Never force-push.

## Constraints

- **Do not duplicate existing systems** — checkpoint, budget, planner, ingestion already exist; extend, don't rebuild.
- Project name is **AgentCore** (`AgentCoreEngine` class, with `AgentCoreEngine = AgentCoreEngine` alias for legacy). "Manus Mini" is legacy only; `.manus-mini/` runtime is preserved but new work uses `.agentcore/`.
- Preserve conventions: `snake_case` modules, `PascalCase` classes. Inspect `git status`/`git diff` and check for secrets before committing.
