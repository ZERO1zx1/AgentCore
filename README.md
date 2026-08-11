# Manus Mini

> **Understand the task. Choose the right execution strategy. Spend intelligently. Produce real work. Preserve progress. Resume instead of restart.**

**Manus Mini** is a universal autonomous work and builder framework designed for high-efficiency, budget-aware execution. It implements a robust agentic engine capable of handling software repositories, large documents, and structured data while protecting the user's execution budget through incremental checkpointing and capability-aware routing.

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
| **PDF Processing** | Supported | Real parsing via `pypdf`, chunking, and hashing |
| **Repository Analysis** | Supported | File tree inspection, manifest detection |
| **Budget Safety** | Supported | Decimal-safe accounting, P0-P4 prioritization |
| **Task Resumption** | Supported | SHA-256 fingerprinting, V2 Task Manifests |
| **Image Analysis** | Experimental | Requires configured multimodal provider |
| **Video Analysis** | Planned | Requires external multimodal provider |

---

## Key Features

- **Universal Task Engine**: Orchestrates complex multi-step workflows with a real Planner and Scheduler.
- **Budget State Machine**: Dynamically manages states from `NORMAL` to `EXHAUSTED` with a 15% emergency reserve.
- **Capability-Aware Router**: Selects the most cost-effective capable model tier for every operation.
- **Atomic Checkpointing**: Ensures every meaningful unit of work is persisted, enabling seamless task resumption.
- **Decimal-Safe Accounting**: Prevents floating-point errors in budget tracking across task resumes.
- **Injectable Registry**: Support for custom model configurations and fake executors for testing.

---

## Quick Start

### Run Validation Suite
```bash
python3 -m unittest discover tests -v
```

### Basic Usage
```python
from src.core.engine import ManusMiniEngine
from src.core.task import TaskInput
from src.core.modes import ExecutionMode

# Initialize with default FakeExecutor for safety
engine = ManusMiniEngine()
task = TaskInput(
    prompt="Analyze this repository",
    task_id="task_001",
    execution_mode=ExecutionMode.AUTO,
    budget=10.0
)

engine.initialize_task(task)
engine.run_to_completion()
```

---

## License
MIT License.
