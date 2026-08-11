# Manus Mini

> **Understand the task. Choose the right execution strategy. Spend intelligently. Produce real work. Preserve progress. Resume instead of restart.**

**Manus Mini** is a universal autonomous work and builder framework designed for high-efficiency, budget-aware execution. It implements a robust agentic engine capable of handling software repositories, structured data, and parsed documents while protecting the user's execution budget through incremental checkpointing and capability-aware routing.

---

## Core Execution Modes

Manus Mini provides three primary execution strategies to suit different task requirements:

| Mode | Philosophy | Best For |
| :--- | :--- | :--- |
| **AUTO** | Dynamic Efficiency | General-purpose tasks and daily workflows |
| **FULL** | Maximum Quality | Complex engineering and high-stakes research |
| **CREDIT_SAFE** | Budget Protection | Large-scale processing and cost-constrained tasks |

---

## Support Matrix

| Capability | Status | Implementation |
| :--- | :--- | :--- |
| **Text Processing** | Supported | Deterministic Python & LLM Routing |
| **PDF Processing** | Supported | Real parsing via `pypdf`, chunking, and hashing (requires `requirements.txt`) |
| **Repository Analysis** | Supported | File tree inspection, manifest detection |
| **Budget Safety** | Supported | Decimal-safe accounting, P0-P4 prioritization |
| **Task Resumption** | Supported | SHA-256 fingerprinting, V2 Task Manifests |
| **Image Analysis** | Experimental | Requires configured multimodal provider |
| **Video Analysis** | Planned | Requires external multimodal provider |

---

## Installation & Dependencies

Install required dependencies for PDF processing and document ingestion:
```bash
pip3 install -r requirements.txt
```
If `pypdf` is unavailable, PDF processing operations will raise a `BLOCKED` error rather than returning placeholder text.

---

## Executor Architecture

Manus Mini uses an injectable `OperationExecutor` interface:
- **`FakeExecutor`**: Used by default for unit testing and offline demonstrations. It does **not** perform real autonomous model execution.
- **`ProductionProviderExecutor`**: An extensible interface template. Applications performing real production work must supply a configured provider adapter implementing `OperationExecutor`.

### Quick Start (Demo with FakeExecutor)
```python
from src.core.engine import ManusMiniEngine
from src.core.task import TaskInput
from src.core.modes import ExecutionMode
from src.core.executor import FakeExecutor

# Engine defaults to FakeExecutor for offline safety
engine = ManusMiniEngine(executor=FakeExecutor())
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

## License
MIT License.
