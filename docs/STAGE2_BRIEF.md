# Stage 2 brief: schema validation (thin version)

Read with `docs/PROJECT_CONTEXT.md` and ADRs 0007, 0008, 0009. This file is the plan and the decision register for this stage only. Update it at the end of every working session (changes only).

## Goal and definition of done

Stage 2 reads the verified raw file through the shared helper, checks the header contract from the config, and returns a typed result or raises `SchemaValidationStageFailed`. Done when:
- `python main.py` runs ingestion then stage 2 successfully and then exits 1 at the sentinel (ADR 0004), with the sentinel moved after stage 2;
- a missing required column makes the run exit 3 with a clear log line;
- the full test suite is green, including one real-ingestion plus real-stage-2 integration test;
- `PROJECT_CONTEXT.md` Status and this file are updated and committed.

## Decision register

DECIDED (settled by the owner; do not reopen unless it contradicts the code):

| ID | Decision | ADR |
|---|---|---|
| D1 | Stage 2 owns a frozen input dataclass; `pipeline.py` adapts config into it; `required_columns` is a tuple; clock is a separate optional argument | 0007 |
| D2 | Result is structured: `dataset` (None on failure), `extra_columns`, coded `violations` | 0007 |
| D3 | The schema block stays in `pipeline.yaml`; later: models to `src/config/`, separate schema file, ODCS post-project | 0008 |
| D4 | Tolerant policy: missing required fails; extras allowed and recorded; order ignored | 0008 |
| D5 | Stage 2 checks the header contract only; row-level work is stage 3 | 0008 |
| D6 | Value-level invariants are declared in config and enforced generically in stage 3 | 0008 |
| D7 | `SchemaValidationStageFailed(StageFailed)`, one subclass per stage, narrows `.result` | 0007 |

FLAGGED (approved defaults to re-review with the assistant BEFORE the step that depends on them; the assistant gives the decision, the strongest counter-argument and a recommendation, and the owner confirms or changes it):

| ID | Default | Main alternative | What would flip it | Revisit before |
|---|---|---|---|---|
| F1 | Ingestion exposes facts as an ingestion-owned success-only frozen type on `IngestionResult` (confidence low-medium) | Flat path/sha256/size fields on `IngestionItemResult` (option G) | Owner wants the smallest diff; `IngestionResult` gets flattened | Step 3 |
| F2 | `DatasetRef` gains `columns` (tuple) and is frozen | Keep it as is and return names separately | A reason not to touch the shared type | Step 2 |
| F3 | One reader: stage 2 uses only `build_dataset_ref`; BOM, blank-line count and error translation deferred | Stage-owned header reader | `row_count` made lazy; BOM files appear sooner than expected | Step 5 |
| F4 | `required_columns` lists all 21 columns now; allowlist field deferred; rule recorded | Minimal list plus a separate `feature_columns` field now | Listing 21 names becomes a burden | Step 1 |
| F5 | Determinism: declared order for missing, header order for extras, tuples | Alphabetical sort | Want results stable under input reordering | Step 5 |
| F6 | Two violation codes (`MISSING_COLUMN`, `EMPTY_DATASET`); 0-byte file gives missing-per-column then empty | Add `UNREADABLE`, duplicate labels, gating now | Pinned file is swapped for an unknown file | Step 5 |
| F7 | Record `columns` and `schema_hash`; no comparer | Compare with a baseline now | Byte pin relaxed; scheduled runs; second dataset | Step 6 |
| F8 | Exit 3 is "stage-defined" (ADR 0009); no "Retry?" README column | Distinct retryable exit code or a flag now | A scheduler needs it | Step 10 |
| F9 | Run record deferred (direction: injected recorder, with `PipelineResult`) | Persist once from `main.py` | Runs stay short and are never killed | Not in this stage |
| F10 | Accept that a header plus a blank line gives `row_count == 1` (EMPTY_DATASET misses it) | Fix the helper's counting now | Stage 3 or a later row-count comparison trips on blank rows | Step 6 |
| F11 | Integration tests patch `src.storage.storage.get_project_root` and use a filename different from the real dataset's | Patch `get_raw_data_path` | Root lookup becomes injected | Step 8 |

## Build order (thin)

Do one step per working session block. Commit after each step with the suite green.

- **Step 0 (optional chore, own commit): config-copy fix.** `write_run_metadata` re-reads the config. Read the text once there, recompute its SHA-256, raise `ConfigurationError` if it differs from `context.config_sha256`, and write the copy with `newline="\n"` so the saved bytes hash to `config_sha256`. No signature changes. Two tests in `tests/test_main.py`: the copy's bytes hash equals the digest; a config edited after hashing is rejected.
- **Step 1: config.** List the 21 columns (below) in `config/pipeline.yaml` `required_columns` (flow style). Add `SchemaConfig` validators: `target_column` must be in `required_columns`; no duplicate names; violations are `ConfigurationError` (exit 2). Tests in `tests/test_main.py`. Done when the suite is green and `python main.py` still reaches ingestion.
- **Step 2: `DatasetRef`.** Add `columns: tuple[str, ...]`, make it frozen, populate it in `build_dataset_ref` from the header. Update `tests/core/test_types.py`. Done when the suite is green.
- **Step 3: ingestion output (F1).** Expose verified-file facts (path, SHA-256, size) per ADR 0007, with tests: present on success, absent on failure and on corrupt. `pipeline.py` stops discarding the return value. Note stale comments in `ingestion.py`.
- **Step 4: stage 2 types** in `src/schemas/schema_validation_stage.py`: frozen input, violation type with a code enum, result, `SchemaValidationStageFailed`.
- **Step 5: pure comparison function** (names in, violations and extras out) with parametrized tests: valid; missing (declared order); extras (header order); reordered; case variant fails; whitespace-padded fails; header-only file; 0-byte file (missing per column, then empty); required list order preserved.
- **Step 6: the stage `run(inp, clock=None)`.** Build the ref through `build_dataset_ref`, compare, finish the result, log violations at ERROR, raise on violations. Tests with `tmp_path`: valid; missing column; extras; empty file; header only; a ragged row passes; a non-numeric or blank value in a numeric-looking column passes (boundary-locking); failure result has status FAILED and `dataset` None.
- **Step 7: pipeline wiring.** Map ingestion output and config into stage 2's input; call stage 2; move the ADR 0004 sentinel after it and update its message and its test (the one that matches "after ingestion"); add a fail-fast proof test (stage 2 raises, the sentinel is never reached). Update `tests/pipelines/test_pipeline.py`.
- **Step 8: integration test** (`tests/pipelines/`, marker `integration` if registered): real ingestion plus real stage 2, `requests.get` patched, `src.storage.storage.get_project_root` patched to `tmp_path`, a different dataset filename, expected hash computed in the test. Scenarios: valid; required column missing with a matching hash (stage 2 fails, exit path 3); hash mismatch (stage 2 never runs); network error (stage 2 never runs).
- **Step 9: real run.** `python main.py`; check the artifact folder and the exit code.
- **Step 10: docs.** Update `PROJECT_CONTEXT.md` Status and Known issues, this file's flagged items (confirmed or changed), the README exit-code text if needed (no "Retry?" column), add or update ADRs for any changed decision, commit.

## Out of scope (do not build in the thin version)

BOM handling; skipping blank rows in the count; translating decode and csv errors; gate-then-collect; duplicate and blank header checks; near-match hints; the run record and persisting `PipelineResult`; retry or failure-kind data; the stage-5 allowlist field; per-column types; the schema-hash comparer; mypy, ruff or Windows CI changes; success/failure result split; moving config models. All are in `docs/BACKLOG.md`.

## Data facts

The Telco file header (21 columns, in file order): customerID, gender, SeniorCitizen, Partner, Dependents, tenure, PhoneService, MultipleLines, InternetService, OnlineSecurity, OnlineBackup, DeviceProtection, TechSupport, StreamingTV, StreamingMovies, Contract, PaperlessBilling, PaymentMethod, MonthlyCharges, TotalCharges, Churn. No BOM; the last line is a data row; 11 `TotalCharges` values are blank (stage 3's concern, must pass stage 2).

## Test and style notes

- New tests live in `tests/schemas/` with an `__init__.py` (most sibling folders have one). Mirror `src/`.
- Annotate every test function; use `tmp_path`; compare tuples, never sets; inject the clock.
- Never write to the real `data/raw/` from a test.
- Known traps: `succeeded[0]` indexing if option G is chosen; `frozen=True` is shallow, so use tuples; `Optional` fields must be narrowed in `pipeline.py`.

## Working protocol for each step

1. The assistant restates the step in two lines and names any FLAGGED item it depends on.
2. For a flagged item: decision, strongest counter-argument, recommendation. The owner confirms or changes it.
3. The assistant gives the exact change and the reason. The owner writes the code.
4. The owner runs the tests and pastes only failing test names and the last 30 lines of the traceback.
5. After each step, commit. At the end of a session the assistant produces changes-only updates for `PROJECT_CONTEXT.md` and this file.
