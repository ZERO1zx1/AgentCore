# Credit-Safe Agent

> **Do the work. Spend intelligently. Preserve progress. Resume instead of restart.**

The **Credit-Safe Agent** is a production-style, budget-aware autonomous execution engine designed to prevent catastrophic budget exhaustion during LLM-driven agentic workflows. Built upon a modular architecture, it combines intelligent cost estimation, multi-tier capability-aware model routing, rigorous checkpointing, task manifest persistence, and emergency reserve protection.

---

## The Problem

Traditional autonomous agents operate without budget awareness. When an agent processes large repositories, massive PDF documents, or complex multi-step workflows, it often exhausts its execution credits mid-task. As a result, all previously completed work, intermediate extractions, and partial generations are lost, forcing the user to pay again from scratch.

---

## Key Features

- **Budget State Machine**: Dynamically manages execution states (`NORMAL`, `CONSERVE`, `CRITICAL`, `EMERGENCY`, `EXHAUSTED`) based on starting budget, remaining balance, and estimated operation costs.
- **Emergency Output Reserve**: Secures a dedicated budget percentage (default 15%) solely for saving results, writing checkpoints, and generating resume manifests.
- **Capability-Aware Multi-Tier Model Router**: Selects the cheapest model capable of reliably completing the operation across tiers (`tier0` local deterministic up to `tier4` advanced reasoning/multimodal).
- **Persistent Task Manifest & Checkpoint Manager**: Checkpoints completed atomic units and maintains a structured task manifest for seamless resumption.
- **Graceful Budget Exhaustion**: Stops expensive operations safely when budget thresholds are breached, preserving partial outputs and exact resume points.

---

## Architecture Overview

```
User Request --> Input Analyzer --> Task Planner --> Cost Estimator --> Budget Manager
                                                                          |
                                       +----------------------------------+
                                       v
                             Budget Watcher State:
                             [NORMAL] --> [CONSERVE] --> [CRITICAL] --> [EMERGENCY] --> [EXHAUSTED]
                                                                                            |
                                                                                Graceful Exit & Resume Manifest
```

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
|   |-- core/
|   |-- budget/
|   |   `-- state.py
|   |-- models/
|   |   `-- router.py
|   |-- checkpoint/
|   |   |-- manifest.py
|   |   `-- manager.py
|   `-- output/
|       `-- manager.py
`-- tests/
    `-- test_credit_safe.py
```

---

## Quick Start & Testing

Run the test suite to verify budget state transitions, emergency reserve protection, model routing, and checkpoint persistence:

```bash
python3 -m unittest discover tests
```

---

## License

MIT License.
