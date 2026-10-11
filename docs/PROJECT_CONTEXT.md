# Project context

Single source of truth for anyone (human or AI assistant) starting work on this repo. Keep it short and current: update it at the end of every stage. Decisions and their reasoning live in `docs/decisions/`.

Last verified against code: 2026-10-11 (`main.py`, `pipeline.py`, `types.py`, `ingestion.py`, `manifest.py`, `storage.py`, `utils/ingest.py`, `config/loader.py`), `config/pipeline.yaml`, the test suite, and `.github/workflows/ci.yml`.

**Read order for a new session:** this file, then the ADRs in `docs/decisions/` (check `Status` and `Superseded by`), then the code. Treat code and tests as the final authority if anything here disagrees, and fix this file.

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
| `src/ingestion/manifest.py` | `IngestionManifest`: append-only JSONL log. A line is written only at a terminal outcome (verified / corrupt / failed); `start_run` is held in memory |
| `src/storage/storage.py` | Project-root discovery (anchored on `requirements.txt`), directory helper, path-traversal-safe raw-data path (`data/raw/<filename>`) |
| `src/utils/ingest.py` | `calculate_sha256`, `download_stream` (writes a `.part` file, then `Path.replace` into place) |
| `src/config/loader.py` | `load_yaml_config` returns `(raw_text, parsed_dict)` |

## Conventions

- A stage returns a `StageResult` subclass. If it ran but did not succeed, it raises a `StageFailed` subclass carrying that result.
- A stage declares the typed input it needs; `pipeline.py` adapts config into it. Stages never import the config schema (dependencies point one way: `main` -> `pipeline` -> stage). A layer calls only the layer directly beneath it.
- Fail fast: a stage failure stops the run; later stages never run on a failed upstream (ADR 0005). Fail loudly: an incomplete pipeline must never look successful (ADR 0004).
- Values that must not change mid-run are frozen dataclasses.
- Anything that reads the environment (clock, argv) takes an optional injected parameter, defaulting to the real one.
- Resolve a path first, then check it is inside its base directory.
- Do not model "primary plus fallback source" as two list entries; a list means "fetch all". Fallback needs explicit failover logic.
- The pipeline-level result will hold stage results, not inherit `StageResult` (ADR 0006).
- Tests mirror `src/`. Network and filesystem boundaries are mocked. Run: `pytest --cov=src --cov=main --cov-report=term-missing`. A fix is not done until the full suite has been run, not just the new test.
- Windows gotcha: use `Path.replace`, not `rename`, when the target file may already exist. Reading a directory as a file raises `IsADirectoryError` on Linux but can surface as `PermissionError` on Windows; tests accept either.
- The editor runs strict Pylance and mypy. Annotate test functions (`tmp_path: Path`, `caplog: pytest.LogCaptureFixture`, mocks as `MagicMock`, `-> None`) or relax strictness per file (undecided).

## Working rules for AI assistants

- Do what was asked. If you see something outside the request, report it as a finding; do not change it silently.
- Review in tiers: blocking, should-fix, minor. Name the file and line for each.
- Diagnose at code level and say what you verified by running versus by reading.
- When a decision is made, propose an ADR in the same format as the existing ones; do not edit an accepted ADR, supersede it.

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

1. How does the verified raw file reach stage 2? (A) `IngestionResult` carries a `DatasetRef`; (B) the orchestrator builds the `DatasetRef` after ingestion succeeds. Leaning B: it keeps ingestion small and the stage-to-stage wiring in one place. Caveat found in code: `pipeline.py` currently discards ingestion's return value, and `IngestionItemResult` holds the filename but not the resolved output path. Under B, `pipeline.py` would have to rebuild `data/raw/<filename>` itself, a second place that knows where ingestion writes. Option C: add `path: Path` to `IngestionItemResult`, and have the orchestrator call `build_dataset_ref(result.succeeded[0].path)`. Decide, then record it as ADR 0007.
2. Scope: structure only (required columns present, target among them) or also types? Leaning structure only. `SchemaConfig` already has `target_column` and `required_columns`, so structure-only needs no new config fields; types would. Note `config/pipeline.yaml` lists only `customerID` and `Churn` as required, so a structure check would pass a file missing most feature columns; decide whether to list every column later stages need.
3. Extra columns beyond the required ones: allow, warn, or reject? Read only the CSV header or the whole file? (`build_dataset_ref` already reads the whole file to count rows.)
4. Failure type: `SchemaValidationFailed(StageFailed)`, which gives exit code 3 for free.

## Known loose ends

- `write_run_metadata` (main.py) re-reads the config file to write `pipeline.yaml`, while `config_sha256` was computed from the text read earlier by the loader. If the file changed between the two reads, the copy would not match the hash. Fix: write the copy from the same `raw_text` (or re-hash and compare).
- `requirements.txt` is a broad environment freeze (mlflow, scikit-learn, fastapi and others are listed but not yet used). Trim it as stages land. Project-root discovery is anchored on `requirements.txt`, and `test_storage` asserts the real root contains it, so keep that file (or change the anchor and the test) when restructuring.
- An ingestion run that is killed mid-download leaves no manifest line. This is by design (a test pins that `start_run` writes nothing); decide whether that is acceptable for audit.
- `manifest.start_run` records the bare filename as `local_path`, not the resolved path under `data/raw/`.
- When stage 2 lands, add a test that it is not called when ingestion raises (ADR 0005); today `test_run_pipeline_propagates_ingestion_failure` cannot show that.
- Two test comments describe superseded behavior: the cross-instance manifest append rationale in `test_manifest.py` (ADR 0003 made manifests per-run) and a "FIX VERIFICATION" note in `test_types.py`.
- Every run currently prints a traceback for the intentional `NotImplementedError` (ADR 0004).
- Log timestamps use local time but carry a `Z` suffix (cosmetic).
- CI (`ci.yml`) runs only `pytest -v`: no coverage run (the documented command uses `--cov`), no mypy, no lint. It installs the full `requirements.txt` freeze with no pip cache, so a package that does not install on Ubuntu would break CI. It triggers on both `push` and `pull_request`, so a PR branch runs twice.
- Docker, MLflow, and S3 are deferred until the pipeline has something real to ship.

## Decision records

- `0001` Ingestion takes a single typed item
- `0002` `StageFailed` base exception and exit code 3
- `0003` Ingestion manifest lives in the run's artifact directory
- `0004` A partial pipeline fails loudly (temporary)
- `0005` A stage failure stops the run (fail fast)
- `0006` The pipeline-level result composes stage results

Format and rules: `docs/decisions/README.md`. Earlier decisions (config validation, run context, safe paths) are visible in the code and README. Backfill ADRs for them when convenient.

## Keeping this file useful

At the end of each stage, update Status and Open questions, add an ADR for each real decision, update "Last verified", and commit. Keep this file under roughly two pages; move detail into ADRs or code comments instead of growing it. The long post-mortem is a retrospective, not current state; do not load it into agent sessions by default.
