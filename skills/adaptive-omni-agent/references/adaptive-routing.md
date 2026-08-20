# Adaptive routing

## Capability dimensions

Select a tool or model only after identifying the required dimensions:

- exact code execution or deterministic transformation;
- programming language/framework fluency;
- context size and repository navigation;
- vision, OCR, layout, slide, or design understanding;
- audio transcription or acoustic interpretation;
- video frame, temporal, or editing capability;
- tool use, browser/UI control, network access, or current web knowledge;
- structured output, latency, privacy, and cost ceiling.

Filter incapable routes before optimizing cost. A cheap route that predictably retries is not efficient.

## Prompt-to-work-unit record

For non-trivial work, maintain a compact record:

```text
objective: one observable outcome
evidence: prompt + relevant workspace facts
assumptions: reversible, low-risk inferences
units: id, dependency, P0-P4, route, validation, checkpoint
limits: authorization, budget/reserve, time, storage, external access
done: verified artifacts and results
next: exact resumable action
```

## Domain transitions

Validate changed boundaries. Examples:

- design/image → frontend asset → application bundle → browser rendering;
- schema/migration → service → API contract → client behavior;
- source → container → CI workflow → hosting plan;
- data → analysis → chart → slide/document export;
- script/model output → encoded audio/video → playable deliverable.

Do not validate every unrelated subsystem. Expand only when a boundary failure or dependency requires it.

## Escalation rules

Escalate capability when a route lacks a required modality/context/tool, local evidence remains genuinely ambiguous, or one bounded attempt exposes a specific deficiency. De-escalate when deterministic tooling can finish or verify the unit. Never escalate solely because the task sounds important.
