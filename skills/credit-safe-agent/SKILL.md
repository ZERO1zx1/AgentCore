---
name: credit-safe-agent
description: Execute useful, resumable work under uncertain or explicit cost limits while preserving an emergency reserve.
---

# Credit-Safe Agent

Preserve a configurable 15% reserve by default. Plan dependency-aware P0–P4 units; use deterministic local paths first, then the least costly capable route. Re-evaluate after every paid operation and checkpoint each completed atomic unit. Do not repeat an identical paid failure without a changed hypothesis.

Record cost as provider-confirmed, estimated, or unknown. Never treat estimates as billing, spend the reserve on exploration/polish, or use remaining budget as authorization for external mutations. At emergency/exhausted state, stop new paid work, persist usable state, and report precise resume requirements. See [budget control](references/budget-control.md).
