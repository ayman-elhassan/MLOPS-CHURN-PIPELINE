# Backlog

Deepening work and loose ends that are not needed to start the current stage. Not attached to assistant sessions by default; ask for it when a stage reaches an item.

## Deepening for stage 2 (after the thin version works end to end)

1. One deliberate change to the shared helper `_read_header_and_count_csv`: open with `utf-8-sig`, skip blank rows when counting, update the pinned test `test_trailing_blank_line_inflates_row_count_by_one`, write an ADR.
2. Translate `UnicodeDecodeError` and `csv.Error` into an `UNREADABLE` violation, wrapping the `build_dataset_ref` call. Let `OSError` propagate (exit 1).
3. Duplicate and blank header label checks; gate-then-collect (unreadable or empty file gives a single violation instead of cascades; the empty-file test changes deliberately); near-match hints such as `customerid` vs `customerID`.
4. Schema-hash comparer against a committed baseline column list, when the byte pin is relaxed, runs are scheduled, or a second dataset appears.
5. Success and failure result shapes instead of an Optional `dataset` ("make illegal states unrepresentable").

## Failure semantics and audit (ADR 0009, ADR 0006)

- Narrow ingestion's catch-all so bugs keep their traceback; record the exception type and HTTP status in the manifest entry.
- A failure-kind or retryable flag on results; a distinct exit code only if a scheduler needs it.
- Run record via an injected recorder and `PipelineResult` persistence (designed together).
- Decide what happens to `IngestionResult.succeeded` / `failed` (ADR 0001 flagged them as odd).

## Later stages

- Stage 3: value-level invariants (uniqueness of `customerID`, allowed `Churn` labels), row width, types, nulls, the 11 blank `TotalCharges` values (check whether they are empty or a single space).
- Stage 5: explicit feature allowlist, a subset of `schema.required_columns`.
- Per-column types and nullability: when a schema file or an ODCS contract is considered.

## Quality gates and tooling

- Add `[tool.mypy]` (strict, `explicit_package_bases = true`, `files = ["main.py", "src"]`) and `types-requests`, `types-PyYAML`; run `mypy` locally first. Likely findings: `**fields` untyped in `_OpenStage.finish`; bare `dict` in `manifest.py`.
- `[tool.ruff]` config; run `ruff check .` locally before adding a CI step. Remove the duplicate `from pathlib import Path` in `storage.py`.
- CI: mypy and ruff steps; a Windows leg; runtime versus dev requirements split (keep `requirements.txt` at the root: project-root discovery and a test depend on it); optional coverage threshold once stable.
- Trim `requirements.txt` (about 100 pins; the code uses requests, PyYAML, pydantic plus dev tools). Consider `pip-tools`.
- Remove `logging==0.4.9.6` from `requirements.txt` (not the standard library; a 2004 backport; required by nothing).

## Housekeeping

- Delete the empty `src/conftest.py`; remove the stray root file `end`; rename or delete `docs/read me.md`; add `tests/core/__init__.py`; align stage folder naming (`schemas/`, `processing/`, `evaluation/` vs `*_stage/`).
- Packaging: code imports `from src.x ...` and tests rely on `pythonpath = ["."]`; a conventional src layout nests a named package. Low priority; ADR if changed.
- Config models could move from `main.py` to `src/config/`, which also removes the `TYPE_CHECKING` import workaround in `pipeline.py`.
- Update the root `README.md` status table and layout when stage 2 lands.
- Log timestamps use local time with a `Z` suffix (cosmetic).
- Docker, MLflow and S3 stay deferred until the pipeline has something real to ship.
