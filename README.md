# MLOps Churn Pipeline

A reproducible, config-driven pipeline for customer churn prediction, built as an end-to-end MLOps project. The goal is a pipeline that can be re-run, audited, and tested stage by stage, not a one-off notebook.

![tests](https://github.com/ayman-elhassan/MLOPS-CHURN-PIPELINE/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.12-blue)

## Status

Early development. The foundation and the first stage are built and tested; the remaining stages are scaffolded but not implemented.

| # | Stage | Status |
|---|---|---|
| 1 | Ingestion | Implemented and tested |
| 2 | Schema validation | Not started |
| 3 | Data quality | Not started |
| 4 | Processing | Not started |
| 5 | Feature engineering | Not started |
| 6 | Splitting | Not started |
| 7 | Training | Not started |
| 8 | Evaluation | Not started |
| 9 | Model validation | Planned |
| 10 | Registration | Planned |
| 11 | Deployment | Planned |

Containerization, experiment tracking, and deployment are planned for after the core pipeline works end to end.

## What works today

- **Validated configuration.** One YAML file (`config/pipeline.yaml`) is loaded and checked with Pydantic. Unknown keys are rejected, and split proportions must sum to 1.0.
- **Run provenance.** Every run gets a unique ID and its own artifact directory containing a copy of the exact config used, the config's SHA-256, and the git commit.
- **Safe paths.** Configured paths are resolved against the project root and rejected if they escape it.
- **Verified ingestion.** The dataset is downloaded as a stream and checked against an expected SHA-256. Each outcome (verified, corrupt, or failed) is appended to a JSONL manifest.
- **Typed stage contracts.** Stages return `StageResult` objects with timing and status, and share a `DatasetRef` type for passing datasets between stages.
- **Distinct failure signals.** A stage that ran and failed (for example, a corrupt download) is reported differently from a configuration error or an unexpected bug.

## Current behavior

`python main.py` runs ingestion for real, then stops with an error and exit code 1. This is intentional: the later stages are not implemented yet, and a partial run must not be mistaken for a complete one.

## Dataset

The pipeline is built around IBM's Telco Customer Churn sample dataset, a public CSV where each row is a telecom customer and the target column is `Churn`. The source URL, filename, and expected SHA-256 are set in `config/pipeline.yaml`, and ingestion verifies the download against that hash before anything else runs.

The data is not stored in this repository. It is downloaded on each run and kept out of version control.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

Use a different config file with `python main.py --config path/to/other.yaml`.

Each run writes to `artifacts/runs/<run_id>/`:

- `pipeline.yaml`: copy of the config used
- `run_metadata.json`: run ID, start time, config hash, git commit
- `ingestion_manifest.jsonl`: one entry per ingestion attempt

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Pipeline completed |
| 1 | Unexpected error |
| 2 | Configuration error |
| 3 | A stage ran but did not succeed (for example, a corrupt download) |

## Project layout

```
main.py                  CLI entry point: config, run context, logging, exit codes
config/pipeline.yaml     The single runtime configuration file
src/
  config/                YAML loading
  core/types.py          StageResult, StageFailed, DatasetRef
  ingestion/             Ingestion stage and its JSONL manifest
  pipelines/pipeline.py  Orchestrator (ingestion wired; later stages pending)
  storage/               Project-root discovery and safe data paths
  utils/                 SHA-256 hashing and streaming download
  schemas/, data_quality_stage/, processing/, feature_engineering_stage/,
  splitting_stage/, training_stage/, evaluation/
                         Scaffolded for upcoming stages
tests/                   Mirrors the src/ layout
.github/workflows/ci.yml Runs the test suite on every push and pull request
```

## Testing

```bash
pytest --cov=src --cov=main --cov-report=term-missing
```

Network calls are mocked, so the suite runs offline.

## Design principles

- **Config over code.** What to run lives in YAML; the code does not hard-code datasets.
- **Fail loudly.** A failed stage raises a typed exception that the entry point maps to an exit code, instead of being swallowed.
- **Reproducibility.** Every run records the config, its hash, and the code version that produced it.
- **One-directional dependencies.** Stages define the input they need, and the orchestrator adapts configuration into it, so stages do not depend on the config schema.

## Notes

`requirements.txt` is currently a full environment freeze. It includes packages the code does not use yet and will be trimmed as the stages are built.
