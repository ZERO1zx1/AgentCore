---
name: adaptive-local-memory
description: Maintain small, evidence-backed local lessons without replacing current workspace inspection.
---

# Adaptive Local Memory

Current files, instructions, versions, and test evidence always outrank recalled lessons. Keep project memory at `<root>/.agent-memory/lessons.jsonl`; recall a small task-and-symptom query before work, and record only reusable outcomes with observable evidence.

Use `scripts/memory.py recall`, `record`, `feedback`, `validate`, `stats`, or `compact` from this skill directory. Store concise abstractions, never secrets, personal data, full prompts, hidden reasoning, or large output. The store is capped at 100 lessons or 512 KiB and compacts atomically. See [memory schema](references/memory-schema.md).
