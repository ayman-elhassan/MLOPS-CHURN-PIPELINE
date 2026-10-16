# Project context

Single source of truth for anyone (human or AI assistant) starting work on this repo. Keep it short and current: update it at the end of every working session. Decisions and their reasoning live in `docs/decisions/`. Detail that is not needed to start work lives in `docs/BACKLOG.md`.

Last verified against code: 2026-10-15 (main.py, pipeline.py, types.py, ingestion.py, manifest.py, storage.py, utils/ingest.py, config/loader.py, config/pipeline.yaml, test names, ci.yml, requirements.txt, pyproject.toml, git ls-files). If this file disagrees with the code or tests, they win: fix this file.

## What this is

A config-driven, reproducible customer-churn pipeline on IBM's Telco Customer Churn CSV (target `Churn`; 21 columns, about 7,000 rows; no byte-order mark; `TotalCharges` has 11 blank values, a stage 3 concern that must still pass stage 2). The goal is a pipeline that can be re-run, audited and tested stage by stage, not a notebook. It is a portfolio project: industry-standard practice first; build a thin end-to-end version first, then deepen. Target for the first end-to-end version: 2026-11-15. Python 3.12; developed on Windows (VS Code, PowerShell); CI runs on Ubuntu (`.github/workflows/ci.yml`).

## How a run works

1. `main.py` parses `--config` (default `config/pipeline.yaml`), loads and validates it into Pydantic models (`PipelineConfig` and sections) and builds a frozen `RunContext` (run id, start time, project root, config path and SHA-256, artifact directory, git commit).
2. It writes `artifacts/runs/<run_id>/pipeline.yaml` (config copy) and `run_metadata.json`.
3. It calls `run_pipeline(config, context)` in `src/pipelines/pipeline.py`, the only module that knows both the config shape and each stage's input shape.
4. Exit codes: `0` success; `1` unexpected error; `2` configuration error; `3` a stage ran and reported failure (`StageFailed`). Code 3 does not say whether a retry would help (ADR 0009).

## Code map

| Path | Role |
|---|---|
| `main.py` | CLI entry, config models, run context, exit codes |
| `src/pipelines/pipeline.py` | Orchestrator; adapts config into each stage's typed input. Imports `PipelineConfig`/`RunContext` only under `TYPE_CHECKING` (circular import with `main.py`) |
| `src/core/types.py` | `StageStatus`, `StageResult` (start/finish), `StageFailed`, `DatasetRef`, `build_dataset_ref` (CSV only), `compute_schema_hash` |
| `src/ingestion/ingestion.py` | `IngestionItem`, `IngestionResult`, `IngestionStageFailed`, `run(item, manifest_path)` |
| `src/ingestion/manifest.py` | `IngestionManifest`: append-only JSONL; a line is written only at a terminal outcome; `start_run` is held in memory |
| `src/storage/storage.py` | Project-root discovery (anchored on `requirements.txt`), `ensure_dir_exists`, `get_raw_data_path` (`data/raw/<filename>`, traversal-safe) |
| `src/utils/ingest.py` | `calculate_sha256`, `download_stream` (`.part` file, then `Path.replace`) |
| `src/config/loader.py` | `load_yaml_config` returns `(raw_text, parsed_dict)` |
| `src/schemas/schema_validation_stage.py` | Stage 2 (an empty file today) |

Other stage folders are empty scaffolds: `data_quality_stage`, `processing`, `feature_engineering_stage`, `splitting_stage`, `training_stage`, `evaluation`. Tests mirror `src/` under `tests/`.

## Conventions

- A stage returns a `StageResult` subclass. If it ran but did not succeed it raises a `StageFailed` subclass carrying that result. A failed stage stops the run (ADR 0005).
- A stage owns the typed input it needs (a frozen dataclass); `pipeline.py` adapts config into it. Stages never import the config schema or another stage. Dependencies point one way: `main` -> `pipeline` -> stage. A layer calls only the layer directly beneath it.
- Values that must not change mid-run are frozen dataclasses. Use tuples inside them (frozen is shallow).
- Fail loudly: an incomplete pipeline must never look successful (ADR 0004).
- The environment is injected: clock and argv are optional parameters that default to the real ones.
- Resolve a path first, then check it is inside its base directory.
- Never iterate a set to produce output. Use declared order or file order, and tuples (ADR 0008).
- A list means "fetch all". Do not model primary-plus-fallback sources as two list entries.
- Tests: `tmp_path`; network and filesystem boundaries mocked; inject clocks. Integration tests must patch `src.storage.storage.get_project_root` (where `storage.py` uses it), not only `main`'s. Run `pytest --cov=src --cov=main --cov-report=term-missing`. A fix is done only when the full suite passes.
- Windows: use `Path.replace`, not `rename`. Reading a directory raises `IsADirectoryError` on Linux but may be `PermissionError` on Windows. The config hash is of newline-normalized text.
- The editor runs strict Pylance and mypy. Annotate test functions (`tmp_path: Path`, `-> None`). mypy configuration is not in `pyproject.toml` yet (see backlog).

## Working rules for AI assistants

- I write the code. Give the exact change (files, names, signatures, behaviour, before/after) and the reason; write full code only when asked.
- Do what was asked, one step at a time. Report anything outside the request as a finding; do not act on it.
- Ask before any architecture decision. Settled decisions live in the ADRs: do not reopen one unless it contradicts the code (show the lines).
- Say whether a claim comes from the pasted code, from a source, or from judgment. Do not run commands (free tier); reason from pasted files and ask for a file by path if it is missing.

## Status

| # | Stage | State |
|---|---|---|
| 1 | Ingestion | Done: built, tested, wired, run end to end |
| 2 | Schema validation | In progress: thin version. Plan and decisions: `docs/STAGE2_BRIEF.md` |
| 3 | Data quality | Empty file |
| 4 | Processing | Empty file |
| 5 | Feature engineering | Empty file |
| 6 | Splitting | Empty file |
| 7 | Training | Empty file |
| 8 | Evaluation | Empty file |
| 9-11 | Model validation, registration, deployment | No files yet |

`python main.py` runs ingestion, then exits 1 by design (`NotImplementedError` sentinel for the remaining stages; ADR 0004).

## Decision records

| # | Title | Status |
|---|---|---|
| 0001 | Ingestion takes a single typed item | Accepted |
| 0002 | `StageFailed` base exception and exit code 3 | Accepted (meaning of 3 clarified in 0009) |
| 0003 | Ingestion manifest lives in the run's artifact directory | Accepted |
| 0004 | A partial pipeline fails loudly | Accepted (temporary) |
| 0005 | A stage failure stops the run | Accepted |
| 0006 | The pipeline-level result composes stage results | Accepted (not yet implemented) |
| 0007 | Stage handoff and shared contracts | Accepted; one provisional item |
| 0008 | Stage 2 scope and policy | Accepted; some items flagged for re-review |
| 0009 | Failure semantics and the run record | Accepted (exit 3); run record deferred |

## Known issues that affect current work

1. `write_run_metadata` (main.py) re-reads the config file, so the saved copy could differ from the hashed text (STAGE2_BRIEF step 0).
2. `build_dataset_ref`: plain utf-8 (no BOM handling), a blank trailing line counts as a row, it scans the whole file, and `DatasetRef` is mutable and has no column names (ADR 0007 and 0008 change some of this).
3. `ingestion.py`: a catch-all `except Exception` turns every failure (timeouts, HTTP errors, disk errors, bugs) into an ordinary failed item without a traceback (ADR 0009). Comments about batches and malformed items are stale after ADR 0001 unless the comment fix was applied.
4. `pipeline.py` discards ingestion's return value. The ADR 0004 sentinel must move after the last built stage, and its test with it.

Everything else is in `docs/BACKLOG.md`.

## Keeping this file useful

At the end of each working session update Status and Known issues, add or update an ADR for each real decision, refresh "Last verified", and commit. Keep this file near two pages; move detail into ADRs or the backlog. The long post-mortem and the stage 2 review files are archives, not current state: do not load them into assistant sessions.
