# AgentCore — OpenCode Project Instructions

## Project Identity

**AgentCore** is a provider-agnostic, budget-aware AI agent execution framework. Implements a robust agentic engine for software repositories, structured data, and parsed documents while protecting execution budgets through incremental checkpointing and capability-aware routing.

**Repository**: `ZERO1zx1/AgentCore`  
**Root**: `C:\Users\hotar\OneDrive\Desktop\ai-agent-skill` (or wherever cloned)

---

## Architecture Overview

```
TaskInput → InputRouter → TaskContext
    ↓
Planner → WorkUnits (P0-P4) → Scheduler
    ↓
ExecutionPolicy → ModelRegistry → OperationExecutor
    ↓
BudgetManager (Decimal-safe) → CheckpointManager
    ↓
ArtifactManager → OutputManager → Resume
```

### Core Components

| Module | Purpose |
|--------|---------|
| `src/core/engine.py` | Main `AgentCoreEngine` orchestrator |
| `src/core/orchestrator.py` | Three-skill intent, artifact, and capability routing |
| `src/core/task.py` | `TaskInput` universal task structure |
| `src/core/planner.py` | `Planner`, `Scheduler`, `WorkUnit` (P0-P4 priorities) |
| `src/core/policy.py` | `ExecutionPolicy` for AUTO/FULL/CREDIT_SAFE modes |
| `src/budget/state.py` | `BudgetManager`, `BudgetState` (NORMAL→EXHAUSTED) |
| `src/budget/estimator.py` | `CostEstimator` for unit cost estimation |
| `src/checkpoint/manifest.py` | `TaskManifest` V3 with skill-route persistence |
| `src/checkpoint/manager.py` | `CheckpointManager` for persistence |
| `src/models/registry.py` | `ModelRegistry`, `ModelSpec` (capability-aware routing) |
| `src/core/executor.py` | `OperationExecutor` contract + `FakeExecutor` |
| `src/ingestion/router.py` | `InputRouter` (repo, PDF, text, JSON/CSV, media/document metadata) |
| `src/memory/store.py` | Bounded read-only runtime recall from adaptive local memory |
| `src/output/artifact_manager.py` | `ArtifactManager` (real file persistence) |
| `src/core/notifications.py` | `GitManager`, `NotificationManager` (auto git push on budget exhaustion) |

### Execution Modes

| Mode | Philosophy | Budget Behavior |
|------|------------|-----------------|
| **AUTO** | Dynamic efficiency | Standard routing, skips P3/P4 at CRITICAL+ |
| **FULL** | Maximum quality | Prefers higher tiers, only skips at EMERGENCY+ |
| **CREDIT_SAFE** | Budget protection | Cheapest capable tier, aggressive skipping |

### Budget States

```
NORMAL (ratio > 0.50) → CONSERVE (≤0.50) → CRITICAL (≤0.25) → EMERGENCY (≤0.10 or ≤reserve) → EXHAUSTED (≤0)
```

- **Emergency reserve**: 15% of initial budget (configurable)
- **Decimal-safe**: All accounting uses `decimal.Decimal`
- **Estimate vs Actual**: `estimated_cost`, `charged_cost`, `actual_cost`, `cost_source` tracked separately

### Checkpoint/Resume

- `TaskManifest` V3 with `schema_version: "3.0"` (loads older manifests)
- Primary/active skills, artifact types, validation routes, and memory-hit IDs persist across resume
- SHA-256 source fingerprinting for change detection
- Granular, dependency-aware invalidation
- Usage history persists across resume
- Manifest saved to `.agentcore/checkpoints/{task_id}_manifest.json`
- Checkpoint retention defaults to the newest 100 task manifests
- Budget-exhaustion Git staging is limited to the explicit checkpoint file; never stage unrelated work

### Provider Abstraction

The engine **only knows**:
- `prompt` — instruction + resolved context
- `capabilities` — what the model must do
- `result` — `ExecutionResult` dataclass
- `usage` — token/cost accounting
- `artifacts` — real files on disk

It does **not** depend on any provider SDK. Implement `OperationExecutor` to integrate real providers.

---

## Important Directories

```
src/                    # Source code (see modules above)
tests/                  # 43 passing tests (unittest-style, pytest compatible)
skills/                 # Three public skills plus internal adaptive-local-memory subsystem
.opencode/              # OpenCode config (skills/, commands/)
.agentcore/             # Runtime storage (checkpoints, tasks, notifications, git_fallback)
.manus-mini/            # Legacy runtime (preserved for compatibility)
.github/                # CI/CD workflows
docs/                   # Documentation
examples/               # Example usage
feat/                   # Feature files
references/             # Reference materials
```

### Runtime Storage (`.agentcore/`)

```
.agentcore/
├── checkpoints/        # TaskManifest JSON files
├── tasks/              # Per-task artifacts & context
│   └── {task_id}/
│       ├── context/    # Persisted source content
│       ├── artifacts/  # Execution outputs
│       └── checkpoints/# Per-task checkpoint copies
├── git_fallback/       # Failed git push payloads
└── notifications.log   # Budget exhaustion log (JSONL)
```

---

## Development Rules

### 1. Understand Before Editing
- Read the target file and its callers/dependencies first
- Trace the real data flow (see architecture above)
- Preserve existing conventions (naming, imports, error handling)

### 2. Validation Commands
```bash
# Run all tests (pytest or unittest)
python -m pytest tests/ -v
# or
python -m unittest discover tests -v

# Run specific test file
python -m pytest tests/test_v2_refined.py -v

# Check imports
python -c "from src.core.engine import AgentCoreEngine; print('OK')"
```

### 3. Git Safety
- Never force-push
- Never discard unrelated user changes
- Inspect `git status` and `git diff` before committing
- Check for secrets in diff

### 4. Budget Accounting
- Never present estimated cost as provider-confirmed billing
- `cost_source: "provider"` = verified, `"estimate"` = not verified
- Emergency reserve (15%) is never spent on optional work

### 5. Naming Conventions
- Project name: **AgentCore** (not "Manus Mini" — legacy only)
- Main class: `AgentCoreEngine`
- Alias: `AgentCoreEngine = AgentCoreEngine` (for compatibility)
- Modules: `snake_case.py`
- Classes: `PascalCase`

---

## Skill System

AgentCore exposes three canonical user-facing skills in `skills/`:

### `skills/adaptive-omni-agent/SKILL.md`
Top-level prompt, artifact, capability, model/tool, and validation orchestration. Uses local memory internally when relevant.

### `skills/code-engineer/SKILL.md`
Autonomous senior software engineering for:
- Repository inspection
- Implementation, debugging, refactoring
- Testing, validation, architecture review
- Performance analysis
- Authorized defensive security review

### `skills/credit-safe-agent/SKILL.md`
Budget-aware autonomous execution:
- Incremental checkpointing
- Emergency reserve protection
- Priority-driven execution (P0-P4)
- Graceful exhaustion & resumability

### OpenCode Skill Integration
Project-local skills exposed via `.opencode/skills/`:
- `.opencode/skills/adaptive-omni-agent/SKILL.md` → wraps canonical skill
- `.opencode/skills/code-engineer/SKILL.md` → wraps canonical skill
- `.opencode/skills/credit-safe-agent/SKILL.md` → wraps canonical skill

Use `/adaptive-omni`, `/code-engineer`, or `/credit-safe` in OpenCode.

---

## Slash Commands (`.opencode/commands/`)

| Command | Purpose |
|---------|---------|
| `/agentcore` | Load project context, show status, identify relevant skills |
| `/adaptive-omni <request>` | Run all three roles through the adaptive orchestrator |
| `/code-engineer <request>` | Run artifact-aware implementation/diagnosis with credit control |
| `/credit-safe <request>` | Run budget-first work with reserve/checkpoint protection |
| `/status` | Show repository, task, checkpoint, budget state |
| `/resume` | Resume from last checkpoint (inspects real persisted state) |
| `/checkpoint` | Manual checkpoint trigger |
| `/test` | Run validation suite |

---

## Test Architecture

- **Framework**: unittest (pytest compatible)
- **Test files**: 8 files, 43 tests
- **Key test areas**: Context delivery, three-skill routing, local-memory recall, media metadata, resume invalidation, cost accounting, dependency/retry, E2E pipelines, PDF, planner, repository

```bash
python -m pytest tests/ -v  # All tests
```

---

## Key Restrictions

1. **Do not duplicate existing systems** — Checkpoint, budget, planner, ingestion already exist
2. **Do not fake provider data** — Label estimates as estimates
3. **Do not hide user data** — `.agentcore/` is inspectable
4. **Preserve compatibility aliases** — `AgentCoreEngine` alias exists for legacy
5. **No force-push** — Ever
6. **Validate with real commands** — Run tests, check imports, inspect diffs

---

## How to Work on AgentCore in OpenCode

### New Session
1. OpenCode reads this `AGENTS.md`
2. Discovers skills via `.opencode/skills/`
3. Loads relevant skill: `/skill code-engineer` or `/skill credit-safe-agent`
4. Inspects current repository state
5. Retrieves relevant `.agentcore/` context if resuming

### Typical Workflow
```
User Request
    ↓
Read AGENTS.md
    ↓
Load relevant skill
    ↓
Inspect repository (grep, glob, read)
    ↓
Trace execution path
    ↓
Research if needed (websearch, webfetch)
    ↓
Implement minimal complete change
    ↓
Run validation (pytest)
    ↓
Fix failures
    ↓
Review diff
    ↓
Checkpoint (auto or /checkpoint)
    ↓
Report verified result
```

---

## Common Tasks

### Run a Task (Demo with FakeExecutor)
```python
from src.core.engine import AgentCoreEngine
from src.core.task import TaskInput
from src.core.modes import ExecutionMode
from src.core.executor import FakeExecutor

engine = AgentCoreEngine(executor=FakeExecutor())
task = TaskInput(
    prompt="Analyze repository structure",
    task_id="demo_task",
    execution_mode=ExecutionMode.AUTO,
    budget=10.0,
    files=["."],
)
engine.initialize_task(task)
engine.run_to_completion()
```

### Resume a Task
```python
from src.core.engine import AgentCoreEngine
from src.core.task import TaskInput
from src.core.modes import ExecutionMode

engine = AgentCoreEngine()
task = TaskInput(
    prompt="Continue analysis",
    task_id="demo_task",
    execution_mode=ExecutionMode.AUTO,
    budget=20.0,  # Add more budget
    resume_task_id="demo_task",
)
engine.initialize_task(task)
engine.run_to_completion()
```

### Run Tests
```bash
python -m pytest tests/ -v
```

---

## Environment

- **Python**: 3.13+
- **Dependencies**: `pypdf>=3.0.0` (PDF processing)
- **Dev dependencies**: `reportlab>=4.0` (test PDF generation), `pytest`
- **No provider SDKs required** (uses `FakeExecutor` by default)

---

## Remaining Limitations

- Real provider execution requires implementing `OperationExecutor` with actual API credentials
- No built-in web search, image/video/audio processing
- No DOCX/XLSX/PPTX support
- Email notifications require SMTP configuration
- Webhook notifications require configured endpoint

---

## References

- Main skill: `SKILL.md` (project root)
- Code Engineer skill: `skills/code-engineer/SKILL.md`
- Credit Safe skill: `skills/credit-safe-agent/SKILL.md`
- README: `README.md`
- Tests: `tests/`
