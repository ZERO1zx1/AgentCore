---
name: agentcore
description: Provider-agnostic, budget-aware, resumable execution for local projects and supplied artifacts.
---

# AgentCore operating guide

Use AgentCore to produce bounded, evidenced work. Inspect current artifacts first, divide the outcome into P0–P4 work units, choose deterministic tooling before a model, then select a model by capability before price.

- Preserve the default 15% reserve and checkpoint meaningful completed work.
- Label costs as provider-confirmed, estimated, or unknown; never present fake-executor output as billing.
- Validate the artifact in its real form and report completed, skipped, blocked, and unverified work separately.
- Treat the three public policy roles as `adaptive-omni-agent`, `code-engineer`, and `credit-safe-agent`; `adaptive-local-memory` is internal, fallible recall.
- Real provider work requires an `OperationExecutor`; AgentCore ships no provider SDK integration.

See [README.md](README.md) for setup, [AGENTS.md](AGENTS.md) for repository conventions, and [references](references/) for the implementation-aligned policies.
