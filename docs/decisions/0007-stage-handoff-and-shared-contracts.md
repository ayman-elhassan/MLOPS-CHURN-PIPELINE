# 0007. Stages hand off typed values: ingestion publishes verified-file facts, stage 2 builds the DatasetRef

- Status: Accepted.
- Date: 2026-10

## Context

- Ingestion proves that the raw file's bytes match a pinned SHA-256. It computes the output path, the hash and the size, but returns none of them, and `pipeline.py` discards its return value.
- A table exists only after the bytes are parsed as CSV. `DatasetRef` (path, row count, schema hash, creation time) describes a table. Nothing consumes it yet, it has no column names, and it is a plain mutable dataclass.
- Stage 2 is the first stage that treats the file as a table. Its input must not import the config schema (ADR 0001) or another stage.

## Decision

1. Ingestion exposes verified-file facts (path, SHA-256, size in bytes) as a small frozen type owned by ingestion. It is carried on `IngestionResult` in an optional field that is set only when the file is verified.
2. `pipeline.py` maps those facts and the config values into stage 2's own frozen input (flat fields; `required_columns` as a tuple). Stage 2 imports neither ingestion nor the config schema.
3. Stage 2 builds the `DatasetRef` by calling `build_dataset_ref` and returns it on its result for stage 3. Ingestion never parses the CSV.
4. `DatasetRef` gains `columns: tuple[str, ...]` and becomes frozen.
5. Stage 2's result is `SchemaValidationResult(StageResult)` with `dataset` (None on failure), `extra_columns` (tuple) and `violations` (tuple of coded violations: code, optional column, message). A failed run raises `SchemaValidationStageFailed(StageFailed)`, which narrows `.result` (ADR 0002).
6. Stage 2's `run` takes an optional clock and passes it to `StageResult.start` and `build_dataset_ref` (injected environment).

## Consequences

- Each layer owns only what it can know: ingestion owns bytes, stage 2 owns the table.
- A file that is verified but not a readable table fails in the schema stage (exit code 3), not in the integrity stage.
- `pipeline.py` stops discarding ingestion's return value and no longer needs to know where ingestion writes.
- The ingestion facts field is Optional because the same class also models failure. `pipeline.py` must narrow it; an assert in the adapter is enough.
- Changing `DatasetRef` touches `core/types.py` and its tests.

## Alternatives considered

- Flat fields (path, SHA-256, size) on `IngestionItemResult`, no new type (option G): the closest rival and the smallest diff. Choose it if you prefer less code or if `IngestionResult` is flattened. Weakness: half-filled states can be represented, and `pipeline.py` would read `succeeded[0]`.
- Ingestion builds the `DatasetRef`: one type, but ingestion would parse CSV and blur integrity failures with shape failures.
- Orchestrator rebuilds the path or the ref: duplicates knowledge of `data/raw/<filename>` or reads the CSV in the orchestrator, and repeats for later stages.
- Stage 2 finds the file by convention: hidden dependency, no lineage.
- A run-level artifact registry: string-keyed shared mutable state, heavy for two stages.
- Putting the file type in `core/types.py`: not needed once stage 2's input is flat.
