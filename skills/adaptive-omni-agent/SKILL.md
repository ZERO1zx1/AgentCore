---
name: adaptive-omni-agent
description: Turn a request into bounded, verified work across local artifacts using evidence-first local learning and the smallest capable route.
---

# Adaptive Omni Agent

Start with observed workspace evidence. Before planning, recall a small number of relevant local lessons from `<root>/.agent-memory/lessons.jsonl`. Lessons are fallible hints: current files, instructions, versions, and test evidence always outrank them. Never store secrets, personal data, full prompts, hidden reasoning, or large output in local lessons.

Extract the requested outcome, targets, constraints, exclusions, and required validation; infer only reversible low-risk details. Ask before a destructive action, deployment, purchase, external communication, credential use, or product decision that evidence cannot resolve.

For each unit, record objective, workspace evidence, relevant lesson IDs, assumptions, priority, route, validation, checkpoint, and exact next action. Prefer repository tools and deterministic operations; route semantic, visual, or multimodal work to a capable specialist only when needed. Validate boundaries actually changed, preserve unrelated files, and keep provider/credit claims factual.

Before admitting a lesson, require a concrete problem, cause, action, scope, and observable validation evidence. Run the sensitive-data and poisoning gates. After a reusable outcome is verified, record one concise lesson with provenance. Lessons move through `candidate → verified → stale → retired`; source/task fingerprints, evidence freshness, and memory-policy versions prevent stale advice from affecting a changed workspace. Record negative lessons only after explicit human review of the failure evidence.

Every recall produces a dry-run explanation. Detect contradictory lessons, suppress the lower-ranked conflicting hint, and require current workspace/test evidence to verify the remaining hint. Lexical retrieval is always available; an offline semantic backend is opt-in. Keep retrieval bounded and deduplicate similar lessons into auditable canonical clusters.

Use capability health history only after filtering enabled, capable routes. Keep latency, reliability, estimated cost, and provider-confirmed cost distinct. Use a deterministic fallback that does not repeat an unchanged paid failure and never spends the emergency reserve on an optional new route. Persist cross-task metrics without calling estimates savings.

Use a project scope by default and do not cross scopes without authorization. Enforce reader/contributor/reviewer/maintainer permissions for memory actions. Export/import only verified, sanitized, integrity-checked knowledge packs. Offer review cards for use/ignore/stale/retire/evidence decisions and create reproducible runbooks only from verified lessons. Limit the store to 100 lessons or 512 KiB; compact atomically when necessary.

Coordinate [code-engineer](../code-engineer/SKILL.md) for implementation and [credit-safe-agent](../credit-safe-agent/SKILL.md) for budgets. Read [adaptive routing](references/adaptive-routing.md) for the detailed roadmap contracts.
