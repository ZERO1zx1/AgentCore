---
name: test
description: Run AgentCore validation suite
---

# /test — Run Tests

Executes the AgentCore test suite with pytest.

## Usage

```
/test [test_file] [--verbose]
```

## Behavior

Runs pytest on the AgentCore test suite:

- `tests/test_context_and_costs.py` — Context delivery, resume invalidation, cost accounting, dependency/retry
- `tests/test_e2e_pipeline.py` — End-to-end pipelines (repo, PDF, resume, usage)
- `tests/test_pdf.py` — PDF processing
- `tests/test_planner.py` — Planner and scheduler
- `tests/test_repo.py` — Repository processing
- `tests/test_v2_refined.py` — V2 refined tests (budget, decimal, resume, modes)

## Default

```
/test
```

Runs all 27 tests with `-v` flag.

## Options

- `test_file` — Specific test file (e.g., `test_v2_refined.py`)
- `--verbose` — Extra verbose output