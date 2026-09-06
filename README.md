# AgentCore

AgentCore is a provider-agnostic, budget-aware execution engine for repositories, text, data, PDFs, and verified media attachments. It plans dependency-aware work units, routes them by capability, records costs with `Decimal`, persists artifacts, and resumes from a task manifest.

> The bundled model registry and `FakeExecutor` are offline demonstrations. They do not call a provider. Real execution requires your own `OperationExecutor` adapter.

## Start here

AgentCore requires Python 3.10+. Install the test dependencies and run the suite:

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest tests -v
```

`pypdf` is the runtime PDF dependency. If unavailable, a PDF task is persisted as `BLOCKED` with `DEPENDENCY_UNAVAILABLE`; AgentCore does not return placeholder extraction.

```python
from src.core.engine import AgentCoreEngine
from src.core.executor import FakeExecutor
from src.core.task import TaskInput

engine = AgentCoreEngine(executor=FakeExecutor())
engine.initialize_task(TaskInput(
    prompt="Inspect this repository and summarize its structure",
    task_id="demo", repository=".", budget=10.0,
))
print(engine.run_to_completion())
```

The demo writes to `.agentcore/tasks/demo/` and `.agentcore/checkpoints/`; its usage is illustrative, not a bill.

## Architecture

```text
TaskInput -> InputRouter -> TaskContext -> AdaptiveOrchestrator
          -> Planner -> WorkUnit graph -> Scheduler -> ModelRouter
          -> OperationExecutor -> ArtifactManager / CheckpointManager -> report
                              ^
                         BudgetManager
```

The public operating policies are [adaptive-omni-agent](skills/adaptive-omni-agent/SKILL.md), [code-engineer](skills/code-engineer/SKILL.md), and [credit-safe-agent](skills/credit-safe-agent/SKILL.md). Adaptive Omni Agent includes bounded, evidence-first local learning; its internal `src/memory` store supplies fallible lessons that never override current workspace evidence. It also provides admission quality gates, recall explanations, conflict handling, provenance/freshness, optional offline hybrid retrieval, route health learning, deterministic fallback, metrics, deduplication, integrity-checked knowledge packs, role permissions, poisoning checks, review cards, and reproducible runbooks.

## Modes and budget safety

| Mode | Intent |
| --- | --- |
| `AUTO` | Practical default; adapts preferred tier to budget state. |
| `FULL` | Prefers stronger coding routes while the budget allows. |
| `CREDIT_SAFE` | Prefers the lowest capable route and drops optional work early. |

The engine reserves 15% of the initial budget by default. It distinguishes `estimated_cost`, `charged_cost`, `actual_cost`, and `cost_source`; only adapter-supplied cost can be provider-confirmed. [Budget policy](references/budget-policy.md) and [execution modes](references/execution-modes.md) describe the exact behavior.

## Provider adapters and inputs

Implement `OperationExecutor.execute(unit_type, model_id, prompt, context)` and return `ExecutionResult`. Register accurate production `ModelSpec` values in an injected `ModelRegistry`. The engine delivers media as verified path descriptors in `context["attachments"]` (path, MIME type, modality, byte size, SHA-256); adapters convert them to their provider format. Binary/base64 content is never appended to prompts.

Repositories, text, JSON/CSV, and PDFs receive built-in routing. Images, audio, video, and office files receive metadata/path routing; semantic processing requires a capable adapter. Read [checkpointing](references/checkpointing.md), [model routing](references/model-routing.md), and the [output contract](references/output-contract.md) before integrating production execution.

### Private local artifacts (Windows)

Set `RuntimeConfig(private_artifacts=True)` to use one private task directory: `context/` stores persisted inputs, `artifacts/` stores generated outputs, and `checkpoints/` stores that task's manifest. On Windows, AgentCore removes inherited ACL entries and grants Full Control to the current Windows identity plus the operating system's `SYSTEM` account. On macOS and Linux, it applies owner-only `0700` permissions. Unsupported platforms, or failed permission changes, fail closed. This does not encrypt data, defeat a Windows administrator who takes ownership, or grant access to another person's device.

## Development and security

Read [AGENTS.md](AGENTS.md) before changing the project. Keep provider keys and notification secrets out of source, manifests, logs, and local memory. Do not authorize purchases or automatically stage unrelated changes during recovery. The low-cost code in [feat/low_cost_skill](feat/low_cost_skill/README.md) is a separate proof of concept, not engine wiring.

## License

MIT License.
