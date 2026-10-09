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

Use `full-scan --deep-research` or `deep-scan` for local dependency/import evidence
and a research plan. Add `--approve-research --request-limit 20` to authorize
bounded public GitHub/PyPI/OSV requests. HTML, JSON, Markdown and black/white
architecture diagrams are written to the date's `reports/deep-research/` folder.
See [Deep Research Scan](../../docs/DEEP_RESEARCH_SCAN.md) for implemented scope,
unknown boundaries and usage limits. JSON stdout contains only JSON; artifact
locations go to stderr.
