# CLI (`src/cli/`)

Command-line interface. Run with `python -m src.cli`.

- `main.py` — argument parsing and command dispatch.
- `__main__.py` — entry point for `python -m src.cli`.
- `__init__.py` — package exports.

Commands: `run`, `list`, `resume`, `mcp`, `skill`, `observe`, `full-scan`.

`full-scan` performs deterministic static triage and prints file/line findings:

```bash
python -m src.cli full-scan --repo .
python -m src.cli full-scan --repo . --mode ci --json
```

Reports are also saved automatically under
`docs/YYYY-MM-DD/reports/<mode>/report.md` and `report.json`, with a date-level
`README.md` describing the folder layout. Use `--output-dir PATH` to choose
another documentation root.
