# Output and reporting contract

Successful units can persist text/code through `ArtifactManager`; their paths are added to the manifest. `run_to_completion()` returns an `OutputManager` report based on that manifest.

| Status | Meaning |
| --- | --- |
| `COMPLETED` | Required work units completed. |
| `PARTIALLY_COMPLETED` | Useful output exists, but required work remains. |
| `BLOCKED` | A dependency or capable model route is unavailable. |
| `FAILED` | Execution failed or attempts were exhausted. |

Reports should state completed and remaining units, saved paths, validation evidence (including checks not run), budget and cost-source evidence, errors, and an exact resume action. Do not call a file validated merely because it exists or call fake usage provider billing. Safe target outputs are relative paths without `..`; absolute/traversal targets are rejected.
