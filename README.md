# Manus Mini

> **Understand the task. Choose the right execution strategy. Spend intelligently. Produce real work. Preserve progress. Resume instead of restart.**

**Manus Mini** is a universal autonomous work and builder framework designed for high-efficiency, budget-aware execution. It evolves the "Credit-Safe" concept into a comprehensive agentic engine capable of handling software repositories, large documents, structured data, and multimodal media while protecting the user's execution budget.

---

## Core Execution Modes

Manus Mini provides three primary execution strategies to suit different task requirements:

| Mode | Philosophy | Best For |
| :--- | :--- | :--- |
| **AUTO** | Dynamic Efficiency | General-purpose tasks and daily workflows |
| **FULL** | Maximum Quality | Complex engineering and high-stakes research |
| **CREDIT_SAFE** | Budget Protection | Large-scale processing and cost-constrained tasks |

---

## Key Features

- **Universal Task Engine**: Orchestrates complex multi-step workflows with built-in planning and scheduling.
- **Budget State Machine**: Dynamically manages states from `NORMAL` to `EXHAUSTED` with emergency reserve protection.
- **Capability-Aware Router**: Selects the most cost-effective capable model tier (`tier0` to `tier4`) for every operation.
- **Atomic Checkpointing**: Ensures every meaningful unit of work is persisted, enabling seamless task resumption.
- **Code-First Delivery**: Prioritizes actual implementation files and working software over conversational prose.
- **Multimodal Routing**: Budget-aware processors for PDF, images, video, and structured data.

---

## Project Structure

```
manus-mini-skill/
|-- README.md
|-- SKILL.md
|-- skills/
|   |-- code-engineer/SKILL.md
|   `-- credit-safe-agent/SKILL.md
|-- src/
|   |-- core/ (Engine, Task, Modes)
|   |-- budget/ (State, Manager, Estimator)
|   |-- models/ (Registry, Router)
|   |-- ingestion/ (PDF, Repository, Multimodal)
|   |-- checkpoint/ (Manifest, Manager)
|   `-- output/ (Report, Rescue)
`-- tests/
```

---

## Quick Start

Manus Mini is designed to be both an integrated framework and a standalone library for budget-aware execution.

### Run Tests
```bash
python3 -m unittest discover tests
```

### Basic Usage
```python
from src.core.engine import ManusMiniEngine
from src.core.task import TaskInput
from src.core.modes import ExecutionMode

engine = ManusMiniEngine()
task = TaskInput(
    prompt="Analyze this repository",
    task_id="task_001",
    execution_mode=ExecutionMode.AUTO,
    budget=10.0
)

engine.initialize_task(task)
engine.execute_step("inspect", "parse", 0.1)
engine.finalize()
```

---

## License
MIT License.
