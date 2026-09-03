# Adapters (`src/adapters/`)

Provider adapters stay external to the engine. This package holds the executor
that translates a work unit into a provider call.

- `provider.py` — `MultiProviderExecutor` (routing by provider/model) and related adapter code.
- `__init__.py` — package exports.

The offline `FakeExecutor` demo lives in `src/core/executor.py`. Real production
integrations are expected to implement `OperationExecutor`.
