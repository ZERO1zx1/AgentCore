---
name: bug-fix-planner
description: Triage a post-analysis findings list, fix only confirmed Critical, High, and clearly reproducible Medium findings with the smallest complete change, and prove each fix with a focused regression test.
---

# Bug Fix Planner

Use after a full repository analysis has produced a findings list where every
finding records severity, confidence, affected files, evidence, impact, likely
root cause, recommended fix, and validation method. Do not start editing before
the analysis exists.

## Triage gate (what may be changed)

1. **Critical / High** with evidence — fix with the smallest complete change.
2. **Medium** — fix only when clearly reproducible (marker `reproducible: true`
   plus evidence of an actual reproduction command/result).
3. Everything else (Low, unverified, speculative) — do **not** modify code.
   Record it as an unverified risk and state the missing evidence.

## Implementation rules

- Implement the smallest complete fix; do not refactor around the bug.
- Do not modify unrelated files; preserve the existing AgentCore architecture
  and pipeline boundaries (`InputRouter` → `Planner`/`Scheduler` →
  `ModelRouter` → `OperationExecutor`, with `BudgetManager` gating).
- Do not modify secrets, credentials, deployment settings, or external
  integrations without explicit approval.
- Do not add web, backend, MCP, or external service dependencies.
- Never commit or push automatically.

## Test and validation order

1. Add or update a focused regression test for **every** code fix.
2. Run focused tests first, e.g. `python -m pytest tests/test_<name>.py -v`.
3. Run the full suite when practical: `python -m pytest tests -v`.
4. For cross-cutting changes also run
   `python -m compileall src plugin feat examples/backend` and the plugin/low-cost
   suites listed in `AGENTS.md`.
5. Review the final `git diff` for unrelated, destructive, or unintended changes.

## Report every implemented fix

For each fix report: original problem, root cause, files changed, exact behavior
changed, tests added or updated, tests actually run, tests not run, remaining risks.

## Deterministic triage

Use `scripts/bug_fix_planner.py` from this skill directory to apply the triage
gate consistently to a list of finding dicts (or JSON lines):

```
python scripts/bug_fix_planner.py --findings findings.json --format table
```

`triage()` splits the findings into `(to_fix, unverified)` so the skill only
edits confirmed targets and explains the rest as unverified risks.