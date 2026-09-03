# Memory (`src/memory/`)

Bounded, evidence-first local memory used by the adaptive-omni-agent skill.

- `store.py` — lesson storage.
- `retrieval.py` — recall with explanations.
- `governance.py` — admission quality gates.
- `safety.py` — poisoning checks.
- `review.py` — review cards.
- `metrics.py` — memory metrics.
- `knowledge_pack.py` — integrity-checked knowledge packs.
- `lifecycle.py` — lesson lifecycle.

Local lessons are fallible and never override current workspace evidence.
