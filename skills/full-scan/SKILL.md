---
name: full-scan
description: Perform a broad repository or project scan with code-engineer, producing an evidence-based file-line report, safe local fixes, validation commands, and clear UX status.
---

# Full Scan

## Deep research handoff

Use `python -m src.cli full-scan --repo . --deep-research` to collect a local
research plan, dependency declarations, duplicate candidates and observed import
architecture. Explain the proposed source scope and request cap before expanding
to external research; prior explicit authorization for that scope is sufficient.
With authorization, add `--approve-research --request-limit 20`.
See [implemented collector scope](../../docs/DEEP_RESEARCH_SCAN.md).

For agent-led deep analysis, read the identified upstream source at its recorded
commit, official release/migration/security documentation, and relevant issue
discussions. Reddit is an optional lead, never sufficient proof of a technical
claim. Separate collected facts, hypotheses, conflicting sources and unknowns.
Record source URL, check date, local path/line and required regression validation.
Review misplaced/duplicate code against module ownership and import impact before
proposing moves. Show observed and proposed architecture separately in black and
white with a legend. Never label the collector itself as provider-backed AI
research or invent tokens/cost. Preserve approval scope and budget reserve.

For the broader agent loop, tool contract, verifier, and observability policy, read [AI Agent Architecture](../../docs/AI_AGENT_ARCHITECTURE.md).

Use this skill with `code-engineer` when the user asks for a full scan, complete audit, broad check, or “what is wrong and how do I run it?”. `full-scan` supplies triage/reporting; `code-engineer` supplies safe implementation and artifact validation.

When no mode is specified, use Strict mode. The agent may propose `FIXED` or `PASS`, but `Confirmed by` remains `PENDING` until the user or an explicitly trusted validation authority confirms it.

## Outcome

Deliver a concise but complete report that distinguishes:

- confirmed defects
- confirmed environment or dependency blockers
- static risks requiring runtime validation
- already-passing areas
- remote or unverified boundaries

Every actionable finding must include the folder, file, and one-based line number when available. If a line cannot be established, use `path:?` and `STATIC-RISK`. Explain the root cause in plain language and provide copy-paste commands for reproduce, fix, and re-validation.

## Workflow

1. Read repository instructions (`AGENTS.md`, `README.md`, package-specific guides) before scanning.
2. Inspect the tree and git status; preserve unrelated user changes.
3. Trace the main data flow before judging isolated lines.
4. Search for security, money/precision, secrets, unsafe process execution, broad exception handling, placeholder behavior, dependency drift, and missing validation.
5. Run the smallest focused validation first, then the repository-required suite. On Windows, redirect test temp data to a known writable project directory when the default temp root is restricted.
6. For web or dependency claims that may have changed, verify with primary official sources only.
7. Do not call a static concern a confirmed runtime bug. Do not call a local repair a deployment.
8. Make local fixes only when the user requests fixing or the request clearly includes full fix. Use `code-engineer` principles: trace producer → transformation → consumer, make the smallest complete change, preserve unrelated work, and add focused regression coverage for non-trivial fixes.
9. Re-run affected tests, inspect the diff, and report exact validation results. Separate code failures from environment, permission, credential, and remote dependency failures.
10. Keep the agent loop visible in UX: show current phase, selected tool, scope/file, validation state, and next action when available.

11. Keep scan artifacts organized. The canonical output layout is:

    ```text
    docs/YYYY-MM-DD/
      README.md
      audit/
      dependencies/
      frontend/
      backend/
      database/
      reports/<mode>/
        report.md       # human-readable report
        report.json     # machine-readable report
      scripts/
    ```

    Do not create date-stamped report files in the repository root or mix
    human reports, probe output, dependency inventories, and SQL results in
    one flat directory. If a companion probe is required, place it under the
    same date directory using a clear subdirectory such as
    `probes/`, `dependencies/`, or `database/`. Re-running the same mode on
    the same date updates its two canonical reports instead of creating
    duplicate files.

## Required report fields

For each finding use this UX-readable schema:

```text
### [N] Short title
- Location          : folder/file.ext:LINE or folder/file.ext:?
- Severity          : CRITICAL | HIGH | MEDIUM | LOW | INFO
- Class             : TEST FAILURE | ENV FAILURE | UNKNOWN
- Root Cause proven : ...
- Root Cause hypoth.: ...
- Confidence        : 0.0–1.0
- Impact            : Scope=... | Blast=... | Timing=... | Recovery=...
- Reproduce         : `<copy-paste command>`
- Fix               : `<copy-paste command or local edit>`
- Re-validate       : `<copy-paste command>`
- Expected / Actual : ... / ...
- Status            : FIXED | BLOCKED | STATIC-RISK | PASS
- Proposed by       : ai-agent
- Confirmed by      : user | PENDING
- Evidence          : command output, exit code, or source evidence
- Boundary Note     : remote/provider/dependency limitation, if any
```

End with:

- commands the user can run from the correct folder
- test totals and failures, including environment-caused failures separately
- changed files
- remaining remote, permission, credential, or dependency boundaries

## Modes

Support these modes when explicitly requested: `strict`, `fast`, `diff`, `regression`, `ci`, and `boundary-only`. In `ci` mode, emit machine-readable JSON in addition to the human report. In `fast` mode, prioritize CRITICAL/HIGH findings. In `diff` mode, restrict findings to changed files. In `boundary-only` mode, inspect only remote, provider, permission, and dependency boundaries.

Never expose secrets, tokens, private prompts, or binary contents in the report. Never claim a provider call, deployment, web result, or full-suite pass without direct evidence.
