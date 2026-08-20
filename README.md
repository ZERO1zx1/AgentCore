# AgentCore

> **Provider-Agnostic AI Agent Execution Framework**

**AgentCore** is a provider-agnostic, budget-aware, resumable AI agent execution framework for cloud models, local models, coding agents, custom runtimes, and future AI providers. It implements a robust agentic engine capable of handling software repositories, structured data, and parsed documents while protecting the user's execution budget through incremental checkpointing and capability-aware routing.

AgentCore is designed to remain independent of any single AI provider, agent platform, or model runtime. External runtimes integrate through the `OperationExecutor` adapter contract.

---

## Architecture: Provider-Agnostic

```text
AI Runtime / Provider
        ↓
OperationExecutor Adapter
        ↓
AgentCore
        ↓
Input / Context / Planner / WorkUnits
        ↓
Budget / Policy / Routing
        ↓
Execution / Artifacts
        ↓
Checkpoint / Resume
```

The engine only knows:
- **prompt** — the instruction + resolved context
- **capabilities** — what the model must be able to do
- **result** — the `ExecutionResult`
- **usage** — token/cost accounting
- **artifacts** — real files persisted to disk

The engine does **not** know or depend on any specific provider SDK (OpenAI, Anthropic, Gemini, Kimi, Ollama, etc.).

### Integration Through OperationExecutor

Any external runtime can be integrated by implementing the `OperationExecutor` contract:

```python
from src.core.executor import OperationExecutor
from src.core.execution_result import ExecutionResult

class MyExecutor(OperationExecutor):
    def execute(self, unit_type, model_id, prompt, context=None) -> ExecutionResult:
        # Call your provider/runtime here
        response = my_provider(prompt)
        return ExecutionResult(
            success=True,
            output_text=response["text"],
            usage={"input_tokens": ..., "output_tokens": ...},
            provider="my-provider",
            model_id=model_id,
        )
```

> **Note**: This is an *integration boundary*, not a built-in provider. Specific providers can be integrated through this adapter; none are claimed to be "fully supported" unless actually tested.

---

## Core Execution Modes

AgentCore execution modes:

| Mode | Philosophy | Best For |
| :--- | :--- | :--- |
| **AUTO** | Dynamic Efficiency | General-purpose tasks and daily workflows |
| **FULL** | Maximum Quality | Complex engineering and high-stakes research |
| **CREDIT_SAFE** | Budget Protection | Large-scale processing and cost-constrained tasks |

---

## Support Matrix

| Capability | Status | Implementation |
| :--- | :--- | :--- |
| **Repository** | Supported | Deterministic file tree, manifests, relevant source selection, SHA-256 fingerprint |
| **Text (TXT/MD)** | Supported | Deterministic reading, chunking, SHA-256 |
| **JSON** | Supported | Local parse, structure metadata, subset extraction |
| **CSV** | Supported | Headers, row/column counts, subset extraction |
| **PDF** | Supported | Real parsing via `pypdf`, chunking, text extraction, hashing |
| **Budget-aware execution** | Supported | Decimal-safe accounting, P0-P4 prioritization, estimate-vs-actual separation |
| **Checkpoint / Resume** | Supported | SHA-256 fingerprinting, V2 Task Manifests, source-change invalidation |
| **Source fingerprint invalidation** | Supported | Granular, dependency-aware invalidation |
| **Real artifact persistence** | Supported | Real files written to `.agentcore/` |
| **Provider adapter contract** | Supported | `OperationExecutor` integration boundary |
| **Real model/provider execution** | Requires external adapter | `OperationExecutor` adapter required |
| **FakeExecutor** | Test/Demo only | Offline deterministic execution, no real model calls |
| **DOCX / XLSX / PPTX** | Not implemented | — |
| **Image / Video / Audio** | Not implemented | — |

---

## Real Context Delivery

WorkUnits receive **actual relevant source content**, not just metadata:

- **Repository tasks**: selected relevant source files (with content) are included in the prompt
- **PDF tasks**: extracted text chunks are persisted and included
- **Text/Markdown tasks**: relevant text chunks are included
- **JSON/CSV tasks**: selected records/headers are included

Context is deterministic and size-limited (`RuntimeConfig` controls `max_context_chars`, `max_file_chars`, `max_chunk_count`).

---

## Cost Accounting

The engine keeps **estimates separate from actual verified costs**:

- `estimated_cost` — estimated before execution (affordability check)
- `charged_cost` — what was actually charged to the budget
- `actual_cost` — provider-reported cost if available
- `cost_source` — `provider` (verified) or `estimate` (not verified)

Estimated cost is **never** reported as provider-confirmed billing.

---

## Installation & Dependencies

Install required dependencies for PDF processing and document ingestion:
```bash
pip3 install -r requirements.txt
```
If `pypdf` is unavailable, PDF processing operations will raise a `BLOCKED` error rather than returning placeholder text.

---

## Executor Architecture

AgentCore uses an injectable `OperationExecutor` interface:
- **`FakeExecutor`**: Used by default for unit testing and offline demonstrations. It does **not** perform real autonomous model execution.
- **`ProductionProviderExecutor`**: An extensible adapter template. Applications performing real production work must supply a configured provider adapter implementing `OperationExecutor`.

### Quick Start (Demo with FakeExecutor)
```python
from src.core.engine import AgentCoreEngine
from src.core.task import TaskInput
from src.core.modes import ExecutionMode
from src.core.executor import FakeExecutor

# Engine defaults to FakeExecutor for offline safety
engine = AgentCoreEngine(executor=FakeExecutor())
task = TaskInput(
    prompt="Analyze repository",
    task_id="task_demo",
    execution_mode=ExecutionMode.AUTO,
    budget=10.0
)

engine.initialize_task(task)
engine.run_to_completion()
```

---

## Task Status

Top-level statuses:

- `COMPLETED`
- `PARTIALLY_COMPLETED`
- `BLOCKED`
- `FAILED`

Reason codes:

- `BUDGET_LIMIT`
- `PROVIDER_NOT_CONFIGURED`
- `DEPENDENCY_MISSING`
- `SOURCE_CHANGED`
- `EXECUTION_ERROR`
- `VALIDATION_ERROR`
- `NONE`

---

## Legacy Compatibility

AgentCore was previously developed under the name "Manus Mini".

Existing imports or runtime paths may remain temporarily supported for backward compatibility:

- `from src.core.engine import AgentCoreEngine` is the standard import
- Legacy `.manus-mini/` runtime data is not deleted; new tasks use `.agentcore/`

---

## License
MIT License.