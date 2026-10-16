# 0009. Exit code 3 is stage-defined; the run record is deferred

- Status: Accepted for the meaning of exit code 3. Deferred for retry classification and the run record.
- Date: 2026-10

## Context

- `_ingest_one_item` catches every exception, including `requests` timeouts and HTTP errors, disk errors, the path-traversal `ValueError` and plain bugs, and records them as a failed item. `run()` then raises `IngestionStageFailed` and `main.py` returns 3. A hash mismatch takes the same route.
- So exit code 3 already mixes transient faults, permanent faults, integrity faults and environment faults. Because of the catch-all, a bug inside that block also loses its traceback, which ADR 0002 promised to keep.
- Ingestion keeps its own per-attempt manifest (ADR 0003). ADR 0006 plans a pipeline-level result that holds stage results.

## Decision

1. Exit code 3 means: a stage ran and reported failure. The reason is in the stage result, the logs and, for ingestion, the manifest. It does not say whether a retry would help. Exit codes stay: 0 success, 1 unexpected error, 2 configuration error, 3 stage failure. Do not add a "Retry?" column to the README.
2. Retry classification (a failure-kind or retryable flag on the result) and any new exit code are deferred. Triggers: a scheduler or retry policy that needs them. A cheap preparation when ingestion is next touched: record the exception type and HTTP status in the manifest entry.
3. Narrowing ingestion's catch-all (so bugs keep their traceback) is in the backlog.
4. The run record is deferred. Direction when built: an orchestrator-owned record per stage (status, duration, counts), written as each stage finishes through a recorder injected into `run_pipeline`, so `pipeline.py` does no file I/O and a crash keeps earlier records. It is designed together with `PipelineResult` (ADR 0006).
5. Reconciliation: the ingestion manifest remains the fine-grained, per-attempt audit (ADR 0003). The run record references manifest run IDs and does not copy their contents. `run_metadata.json` stays write-once and is never edited by stages. ADRs 0003 and 0006 are unchanged.
6. Interim for stage 2: the stage logs its violations at ERROR before raising; `main.py` logs the stage name and duration.

## Consequences

- Automation must not assume that exit code 3 is permanent or retryable.
- Failure details for stage 2 live only in logs until the run record exists.

## Alternatives considered

- A distinct exit code now for retryable failures: needs classification the code does not have (the catch-all discards the exception type), supersedes ADR 0002, and no scheduler needs it yet.
- A retryable or failure-kind flag on the result with exit code 3 unchanged: the usual workflow-engine pattern; invisible to automation that only reads exit codes. Do it first when the need appears.
- Narrowing the catch in ingestion now: restores the traceback promise but changes ingestion behaviour and tests.
- Adopting sysexits numbers: renumbers 2 and 3.
- Accumulating results in `pipeline.py` and persisting once in `main.py`: one edge writer, but the failure path needs a wrapped exception or loses earlier stages, and nothing survives a hard kill.
- A stage-owned manifest per stage: repeats the ingestion pattern for every stage and gives no run-level view.
