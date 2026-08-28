# Memory schema

The store is UTF-8 JSON Lines. `lesson` events include an ID, timestamp, scope, problem, cause, action, evidence, tags, and `candidate` or `verified` status. `feedback` events include the lesson ID, timestamp, success/failure result, and evidence.

Retrieval ranks lexical overlap, boosts verified lessons, increases confidence after success feedback, and reduces it more strongly after failure. Malformed lines are ignored with a warning. At quota, compaction retains the strongest 80 lessons and related feedback using atomic replacement. Run `memory.py validate` after moving or manually editing a store.
