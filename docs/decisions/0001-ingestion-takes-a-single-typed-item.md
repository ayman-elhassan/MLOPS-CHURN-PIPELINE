# 0001. Ingestion takes a single typed item

- Status: Accepted
- Date: 2026-10

## Context

Ingestion originally took a config dict with an `items` list and processed each item in a loop. The pipeline config describes exactly one dataset (`DatasetConfig`: name, url, filename, expected SHA-256), so wiring ingestion into `run_pipeline` needed an adapter between two different shapes. Questions:

1. Keep the list-based interface and wrap the single dataset in a one-item list, or make ingestion accept one item?
2. What type is that item: a plain dict, `DatasetConfig` itself, or a type owned by ingestion?

## Decision

`ingestion.run(item: IngestionItem, manifest_path: Path)` takes one item. `IngestionItem` is a frozen dataclass defined in `src/ingestion/ingestion.py` with `url`, `filename`, and `expected_sha256`. `pipeline.py` builds it from `config.dataset`. The batch loop and the `items` precondition were removed.

## Consequences

- Ingestion never imports the config schema, so a change to `PipelineConfig` touches only the adapter in `pipeline.py`.
- The shape is checkable by mypy and follows the typed-contract style already used by `StageResult` and `DatasetRef`.
- Removed the `safe_get` fallback, the "items is not a list" edge case, and the batch-isolation tests.
- Ingesting several files later means restoring a thin loop with one caller to update; `_ingest_one_item` is unchanged either way.
- `IngestionResult` still holds `succeeded` / `failed` lists (now at most one entry) to limit churn. Revisit if it starts to look odd.

## Alternatives considered

- A plain dict: decoupled but untyped, so a typo'd key only fails at runtime.
- Passing `DatasetConfig` directly: less code, but couples ingestion and its tests to the config schema.
- `Protocol`, `NamedTuple`, `TypedDict`, or a Pydantic model: implicit, loose, or duplicating validation already done upstream.
