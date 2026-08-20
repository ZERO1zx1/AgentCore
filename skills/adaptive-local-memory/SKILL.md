---
name: adaptive-local-memory
description: Recall and maintain evidence-backed local lessons from prior task failures and successful fixes. Use for recurring repository, tool, or workflow tasks where past verified outcomes can prevent repeated mistakes; do not use as a substitute for inspecting current state.
---

# Adaptive Local Memory

Use local experience as fallible evidence, not as authority. The current task, repository instructions, and observed state always outrank stored lessons.

## Before acting

1. Identify a short query from the task, technology, operation, and observed symptom.
2. Locate the workspace root. Keep project-specific memory at `<root>/.agent-memory/lessons.jsonl`.
3. Run `python scripts/memory.py recall --root <root> --query "<task and symptom>" --limit 5`.
4. Apply only lessons whose scope, conditions, and evidence match the present state. Re-check files, versions, commands, and permissions when they may have changed.

No memory hit is a normal result. Continue from primary evidence rather than broadening a weak match.

## After an outcome

Record a lesson only when it is reusable and supported by an observable result. A raw error is not yet a lesson.

```bash
python scripts/memory.py record --root <root> \
  --problem "<stable symptom>" --cause "<demonstrated cause or unknown>" \
  --action "<minimal corrective action>" --evidence "<verification>" \
  --tags "<comma-separated retrieval terms>" --status verified
```

Use `--status candidate` when the cause or fix is not verified. Candidate lessons may inform investigation but must not direct mutations without confirmation.

When a recalled lesson succeeds or fails in a new context, append feedback rather than rewriting history:

```bash
python scripts/memory.py feedback --root <root> --id <lesson-id> --result success --evidence "<new verification>"
```

After a contradiction, use `--result failure`. The retriever automatically reduces confidence in contradicted lessons.

## Small default quota

Keep each project store small: at most 100 lessons and 512 KiB. `record` automatically compacts to the strongest 80 lessons before adding more when either limit is reached. Compaction prefers verified, recently reinforced lessons and removes contradicted or weak candidates first. Run `memory.py stats --root <root>` to inspect usage, or `memory.py compact --root <root>` to compact manually.

## Storage boundaries

- Prefer project memory. Use `--store <explicit-path>` only when the user wants a shared store.
- Never store secrets, tokens, credentials, private keys, personal data, full prompts, or large command output. The script rejects common secret patterns, but inspect content before recording.
- Store concise abstractions and verification evidence, not hidden reasoning or conversation transcripts.
- Do not modify another project's memory without authorization.
- Events are append-only between quota compactions. Compaction uses an atomic replacement and preserves retained lessons with their feedback. Version-control the store only when the user wants shared team memory.

## Quality gate

A useful lesson states the matching condition, demonstrated cause, minimal action, and observable verification. Do not generalize environment failures, one-off typos, or unverified guesses into universal rules. If a lesson conflicts with present evidence, follow present evidence and record failure feedback.

For the event schema and confidence calculation, read [references/memory-schema.md](references/memory-schema.md) only when integrating or debugging the store.
