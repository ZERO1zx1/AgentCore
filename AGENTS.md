# AgentCore contributor guide

## Scope and source of truth

AgentCore is a provider-agnostic, budget-aware execution engine. Inspect source and tests before changing behavior; documentation must reflect implemented behavior, not planned integrations. This working copy is not a Git checkout, so preserve all existing files and review changes directly.

## Architecture

`AgentCoreEngine` coordinates `InputRouter`, `AdaptiveOrchestrator`, `Planner`/`Scheduler`, `ModelRouter`, `OperationExecutor`, `BudgetManager`, `ArtifactManager`, and `CheckpointManager`. `TaskManifest` schema is 3.0. Read [README.md](README.md) and the policy references before changing a boundary.

## Rules

- Use `AgentCore` and `AgentCoreEngine`; “Manus Mini” is legacy runtime data only.
- Keep provider adapters external. `FakeExecutor` and the bundled `fake-*` models are demos, not production integrations.
- Keep `Decimal`-safe accounting; never call an estimate confirmed billing.
- Preserve the default 15% reserve and the checkpoint/resume contract.
- Never commit secrets or auto-stage unrelated files. Budget-recovery Git behavior may stage only the explicit manifest.
- Keep media as verified path attachments; do not inject binary/base64 into prompts.

## Validation

```bash
python -m pytest tests -v
python -m unittest discover tests -v
python -c "from src.core.engine import AgentCoreEngine; print('OK')"
```

Run the smallest relevant check first, then the suite for cross-cutting changes. Report PASS, pre-existing failures, and checks not run honestly. The focused proof-of-concept tests live under `feat/low-cost-skill/tests` and are separate from the engine.

## Local dashboard visibility

For a non-trivial task performed through the AgentCore skill in this workspace,
the **agent**, not the human user, must create an `agentcore skill start`
dashboard record before work begins, update it at a meaningful checkpoint, and
finish or fail it at the end. Keep the returned task ID in the agent's working
context; never ask the user to copy it, type a dashboard command, or perform
status updates. Use only a short, non-sensitive Mongolian
title/message/summary. This is a local progress display, not provider billing
or a cloud connection. The exact agent-only commands are documented in
`SKILL.md`.

## Navigation

- [README](README.md): installation, architecture, and adapter boundary.
- [Public skills](skills/): operating policies and specialist routing.
- [References](references/): execution semantics.
- [Credit management](docs/CREDIT-MANAGEMENT.md): optional application-integration draft.
