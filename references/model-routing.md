# Model routing

`ModelRouter` resolves required capabilities, asks `ExecutionPolicy` for a preferred tier, then asks `ModelRegistry` for an enabled capable model. Price comparison happens only after capability filtering.

The bundled `fake-*` models are deterministic routing fixtures, not provider products or real execution. Default requirements are `parsing` for `parse`, `deterministic` for `test`/`output`, `coding` for `code`, `text` for `analyze`, and `multimodal` for `transform`.

Register real models with accurate capabilities, modalities, per-1,000-token prices, context size, and enabled state. Ensure the corresponding adapter supports any attachment modality. `CostEstimator` is a heuristic and cannot verify provider charges; apply [budget policy](budget-policy.md) for real spend control.
