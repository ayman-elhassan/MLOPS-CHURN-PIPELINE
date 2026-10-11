# Project context

Single source of truth for anyone (human or AI assistant) starting work on this repo. Keep it short and current: update it at the end of every stage. Decisions and their reasoning live in `docs/decisions/`.

## What this is

A config-driven, reproducible customer-churn pipeline built on IBM's Telco Customer Churn CSV (target column `Churn`). The goal is a pipeline that can be re-run, audited, and tested stage by stage, not a notebook. Python 3.12; developed on Windows (VS Code, PowerShell); CI runs on Ubuntu via `.github/workflows/ci.yml`.

## How a run works

1. `main.py` parses `--config` (default `config/pipeline.yaml`), loads and validates it into Pydantic models (`PipelineConfig` and its sections), and builds a frozen `RunContext` (run id, start time, project root, config path and SHA-256, artifact directory, git commit).
2. It writes `artifacts/runs/<run_id>/pipeline.yaml` (config copy) and `run_metadata.json`.
3. It calls `run_pipeline(config, context)` in `src/pipelines/pipeline.py`, the only module that knows both the config shape and each stage's input shape.
4. Exit codes: `0` success, `1` unexpected error, `2` configuration error, `3` a stage ran and failed (`StageFailed`).

## Code map

| Path | Role |
|---|---|
| `main.py` | CLI entry, config models, run context, exit codes |
| `src/pipelines/pipeline.py` | Orchestrator; adapts config into each stage's typed input. Imports `PipelineConfig`/`RunContext` only under `TYPE_CHECKING` (avoids a circular import with `main.py`) |
| `src/core/types.py` | `StageStatus`, `StageResult` (start/finish pattern), `StageFailed`, `DatasetRef`, `build_dataset_ref` (CSV only), `compute_schema_hash` |
| `src/ingestion/ingestion.py` | `IngestionItem`, `IngestionResult`, `IngestionStageFailed`, `run(item, manifest_path)` |
| `src/ingestion/manifest.py` | `IngestionManifest`: append-only JSONL log (start / success / corrupt / failure) |
| `src/storage/storage.py` | Project-root discovery (anchored on `requirements.txt`), directory helper, path-traversal-safe raw-data path |
| `src/utils/ingest.py` | `calculate_sha256`, `download_stream` (writes a `.part` file, then `Path.replace` into place) |
| `src/config/loader.py` | `load_yaml_config` returns `(raw_text, parsed_dict)` |

## Conventions

- A stage returns a `StageResult` subclass. If it ran but did not succeed, it raises a `StageFailed` subclass carrying that result.
- A stage declares the typed input it needs; `pipeline.py` adapts config into it. Stages never import the config schema (dependencies point one way: `main` -> `pipeline` -> stage).
- Values that must not change mid-run are frozen dataclasses.
- Fail loudly: an incomplete pipeline must never look successful.
- Tests mirror `src/`. Network and filesystem boundaries are mocked. Run: `pytest --cov=src --cov=main --cov-report=term-missing`.
- Windows gotcha: use `Path.replace`, not `rename`, when the target file may already exist.
- The editor runs strict Pylance and mypy. Annotate test functions (`tmp_path: Path`, `caplog: pytest.LogCaptureFixture`, mocks as `MagicMock`, `-> None`) or relax strictness per file (undecided).

## Status

| # | Stage | State |
|---|---|---|
| 1 | Ingestion | Done: built, tested, wired, run end to end |
| 2 | Schema validation | Next. `src/schemas/schema_validation_stage.py` is an empty file |
| 3 | Data quality | Empty file |
| 4 | Processing | Empty file |
| 5 | Feature engineering | Empty file |
| 6 | Splitting | Empty file |
| 7 | Training | Empty file |
| 8 | Evaluation | Empty file |
| 9-11 | Model validation, registration, deployment | No files yet |

`python main.py` currently runs ingestion, then exits 1 by design (`NotImplementedError` for the remaining stages; see ADR 0004).

## Open questions for stage 2 (schema validation)

1. How does the verified raw file reach stage 2? (A) `IngestionResult` carries a `DatasetRef`; (B) the orchestrator builds the `DatasetRef` after ingestion succeeds. Leaning B: it keeps ingestion small and the stage-to-stage wiring in one place.
2. Scope: structure only (required columns present, target among them) or also types? Leaning structure only; types would need new config fields, and content problems belong to data quality.
3. Extra columns beyond the required ones: allow, warn, or reject? Read only the CSV header or the whole file?
4. Failure type: `SchemaValidationFailed(StageFailed)`, which gives exit code 3 for free.

## Known loose ends

- `requirements.txt` is a broad environment freeze (mlflow, scikit-learn, fastapi and others are listed but not yet used). Trim it as stages land.
- Log timestamps use local time but carry a `Z` suffix (cosmetic).
- No lint step in CI.
- Docker, MLflow, and S3 are deferred until the pipeline has something real to ship.

## Decision records

- `0001` Ingestion takes a single typed item
- `0002` `StageFailed` base exception and exit code 3
- `0003` Ingestion manifest lives in the run's artifact directory
- `0004` A partial pipeline fails loudly

Earlier decisions (config validation, run context, safe paths) are visible in the code and README. Backfill ADRs for them when convenient.

## Keeping this file useful

At the end of each stage, update Status and Open questions, add an ADR for each real decision, and commit. Keep this file under roughly two pages; move detail into ADRs or code comments instead of growing it.
