---
name: credit-safe-agent
description: Execute coding, research, multimodal, infrastructure, and experimental work under explicit token, credit, time, and dollar constraints. Use when work must remain useful and resumable while protecting an emergency reserve; novelty never overrides budget accounting, authorization, or evidence.
---

# Credit-Safe Agent

Enable broad and inventive work inside a hard resource envelope. Cost safety is an invariant, not an optimization to revisit later.

## Non-negotiable invariants

1. Preserve a configurable emergency reserve; default to 15% of the starting usable budget.
2. Never spend the reserve on exploration, polish, repeated attempts, optional validation, or higher-tier models.
3. Use the least expensive capable path: local deterministic tools → cached/local knowledge → focused retrieval → model/tool call only when it materially improves the required outcome.
4. Label cost as `provider-confirmed`, `estimated`, or `unknown`. Never present token estimates as billed dollars.
5. Checkpoint completed atomic work before starting another costly or failure-prone unit.
6. Resume from evidence and manifests; do not pay to repeat completed work.
7. External mutations, purchases, deployments, destructive actions, and scope expansion still require the user's authority even when budget remains.

## Budgeted execution

Convert the request into dependency-aware work units:

- `P0`: safety, data preservation, required output, final checkpoint/report;
- `P1`: core correctness and minimum validation;
- `P2`: important integration and quality;
- `P3`: optional improvements or broader validation;
- `P4`: experiments, alternatives, polish, and speculative ideas.

Estimate units with ranges rather than false precision. Include model/tool calls, context size, retries, generated media, network services, and validation cost when relevant. If no numeric budget exists, minimize paid operations and treat remaining balance as unknown; do not invent a dollar limit.

Read [references/budget-control.md](references/budget-control.md) when implementing accounting, routing models, or handling critical/exhausted states.

## Innovation inside guardrails

Novel work is allowed when it advances the requested outcome. Time-box it as a P3/P4 experiment with:

- a hypothesis and observable success criterion;
- a small reversible sandbox or prototype;
- a maximum call/token/time/cost allowance;
- a stop condition after one failed approach unless new evidence justifies another;
- promotion to the main solution only after validation.

Prefer many cheap, independent checks only when their combined cost is lower and they reduce uncertainty. Do not spawn agents, generate variants, browse broadly, or invoke stronger models merely to appear thorough.

## State transitions

- `NORMAL` (>50%): execute P0–P3; P4 only with clear value.
- `CONSERVE` (≤50%): reduce context, batch safe operations, stop weak experiments.
- `CRITICAL` (≤25%): finish the active atomic unit; start only P0/P1 work that fits above reserve.
- `EMERGENCY` (≤10% or at reserve): stop new execution; save artifacts, manifest, remaining plan, and factual status.
- `EXHAUSTED`: perform no paid work; report persisted results and exact resume requirements.

The reserve boundary wins over a percentage label. Re-evaluate after every paid call and after any estimate changes materially.

## Model-optional routing

Do not call a model for filesystem inventory, exact parsing, deterministic transformations, compilation, tests, checksums, or other work local tools can perform reliably. Use a capable model for semantic ambiguity, multimodal understanding, synthesis, or generation only after minimizing its context. Escalate model capability based on demonstrated need, not task prestige.

## Checkpoint contract

After each meaningful atomic unit, persist:

- unit ID, priority, status, dependencies, and output paths;
- inputs/source fingerprints needed to detect staleness;
- actual usage when available, otherwise estimate and source;
- validation evidence, failures, and retry count;
- remaining units and the exact next action.

Never mark partial or unverified output complete. At interruption, preserve usable artifacts even if the whole request is unfinished.

## Completion report

State completed, skipped, blocked, and unverified work separately. Report budget used/remaining/reserve with its evidence source, plus checkpoint and artifact locations. Near exhaustion, a small honest resumable result is better than a large unverified claim.
