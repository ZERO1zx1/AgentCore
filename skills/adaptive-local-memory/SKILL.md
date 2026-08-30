---
name: adaptive-local-memory
description: Legacy compatibility alias for Adaptive Omni Agent's evidence-first local-learning capability.
---

# Adaptive Local Memory (legacy alias)

This behavior has been merged into [`adaptive-omni-agent`](../adaptive-omni-agent/SKILL.md). Do not route work here as a separate public skill. Use Adaptive Omni Agent for both orchestration and local learning.

Current files, instructions, versions, and test evidence always outrank recalled lessons. Keep project memory at `<root>/.agent-memory/lessons.jsonl`; recall a small task-and-symptom query before work, and record only reusable outcomes with observable evidence.

Use `scripts/memory.py recall`, `record`, `feedback`, `validate`, `stats`, or `compact` from this skill directory. Store concise abstractions, never secrets, personal data, full prompts, hidden reasoning, or large output. The store is capped at 100 lessons or 512 KiB and compacts atomically. See [memory schema](references/memory-schema.md).
