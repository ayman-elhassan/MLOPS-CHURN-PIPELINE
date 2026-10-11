# 0002. `StageFailed` base exception and exit code 3

- Status: Accepted
- Date: 2026-10

## Context

`IngestionStageFailed` already carried the finalized `IngestionResult`, but `main.py` handled only `ConfigurationError` (exit 2) and a bare `Exception` (exit 1). A stage that ran and failed in an expected way (for example, a corrupt download) was reported exactly like a programming bug.

## Decision

- `StageFailed(Exception)` lives in `src/core/types.py` and carries `result: StageResult`.
- Each stage's failure subclasses it. `IngestionStageFailed` narrows `.result` to `IngestionResult`.
- `main.py` catches `StageFailed` before the bare handler, logs the stage name and duration without a traceback, and returns exit code 3.
- Exit codes: 0 success, 1 unexpected error, 2 configuration error, 3 stage failure.

## Consequences

- `main.py` reacts to a category of failure, so new stages need no changes there.
- Logs and exit codes distinguish an expected failed stage from a bug (which keeps its traceback).
- The order of `except` clauses matters: `StageFailed` must come before `except Exception`.
- Tests: `test_main` asserts exit code 3; an ingestion test asserts `IngestionStageFailed` is a `StageFailed`.

## Alternatives considered

- Let `IngestionStageFailed` propagate to the bare handler: no new code, but it conflates bugs with expected failures.
- A message-only base class: simpler, but `main.py` would lose the result unless it caught each stage's own exception type.
