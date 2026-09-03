# Tests (`tests/`)

The engine test suite. Run:

```bash
python -m pytest tests -v
python -m unittest discover tests -v
```

Covers the engine pipeline, CLI, MCP, memory, budget/checkpoint, private
artifacts, PDF, planner, provider adapter, and the example usage proxy.

The focused low-cost proof-of-concept tests live separately under
`feat/low_cost_skill/tests/`.
