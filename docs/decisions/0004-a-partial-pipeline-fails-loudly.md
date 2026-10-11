# 0004. A partial pipeline fails loudly

- Status: Accepted (temporary: remove when the last stage lands)
- Date: 2026-10

## Context

Only ingestion is implemented. `main.py` logs "Pipeline completed" and returns 0 whenever `run_pipeline` returns, so a run that did one stage of eleven would look like a success to CI or a scheduler.

## Decision

After ingestion, `run_pipeline` raises `NotImplementedError("Stages after ingestion have not been implemented yet.")`. `main.py` handles it as an unexpected error and returns 1.

## Consequences

- An incomplete run can never be mistaken for a complete one.
- Every run exits 1 until the final stage exists, even when ingestion succeeds.
- When a stage is added, move the raise after it. The test that matches on "after ingestion" must be updated at the same time.
- Delete the raise and its test once all stages are implemented.

## Alternatives considered

- Returning quietly after ingestion: would log success and exit 0 for a partial run.
