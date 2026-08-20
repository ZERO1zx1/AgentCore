---
name: code-engineer
description: >
  Autonomous senior software engineering skill for repository inspection,
  implementation, debugging, refactoring, testing, validation, architecture
  review, performance work, and authorized defensive security review. Use when
  the user asks to build, fix, improve, understand, test, or review software.
---

# Code Engineer (OpenCode Wrapper)

This skill wraps the canonical AgentCore skill at `skills/code-engineer/SKILL.md`.

## Usage

```
/skill code-engineer
```

## Behavior

When active, this skill follows the Code Engineer lifecycle:

```
UNDERSTAND REQUEST
       ↓
READ AGENTS.md
       ↓
INSPECT REPOSITORY
       ↓
LOAD RELEVANT HISTORY/CONTEXT
       ↓
TRACE EXECUTION PATH
       ↓
RESEARCH IF NECESSARY
       ↓
FORM IMPLEMENTATION PLAN
       ↓
EDIT REAL FILES
       ↓
RE-READ CHANGES
       ↓
RUN VALIDATION
       ↓
FIX FAILURES
       ↓
REVIEW DIFF
       ↓
CHECKPOINT
       ↓
REPORT VERIFIED RESULT
```

The full skill instructions are in the canonical file: `skills/code-engineer/SKILL.md`

This wrapper exists for OpenCode skill discovery. The canonical skill content is the source of truth.