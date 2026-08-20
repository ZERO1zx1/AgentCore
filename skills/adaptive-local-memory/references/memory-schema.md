# Memory event schema

The store is append-only JSON Lines. Each line is independently parseable UTF-8 JSON.

Lesson events contain `event=lesson`, `id`, `created_at`, `scope`, `problem`, `cause`, `action`, `evidence`, `tags`, and `status` (`candidate` or `verified`). Feedback events contain `event=feedback`, `lesson_id`, `created_at`, `result` (`success` or `failure`), and `evidence`.

Retrieval tokenizes the query and lesson fields, then ranks by lexical overlap. Verified lessons receive a small boost. Success feedback increases confidence; failure feedback decreases it more strongly. Malformed lines are ignored with a warning so an interrupted append does not make earlier memory unusable.

The default project quota is 100 lessons or 512 KiB. At the boundary, compaction retains the strongest 80 lessons and their feedback using atomic file replacement. Use `memory.py validate` to check schema and references, `memory.py stats` for counts and quota usage, and `memory.py compact` for manual cleanup.
