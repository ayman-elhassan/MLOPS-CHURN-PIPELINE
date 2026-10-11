# 0006. The pipeline-level result composes stage results

- Status: Accepted (not yet implemented)
- Date: 2026-10

## Context

Every stage returns a `StageResult` subclass sharing `stage_name`, `status`, `started_at`, `completed_at`, and `duration_seconds`. `run_pipeline` currently returns `object` and discards ingestion's result. Once there is a summary of a whole run, it could either subclass `StageResult` or hold stage results.

## Decision

A pipeline-level result (for example `PipelineResult`) will hold an ordered collection of `StageResult` objects and will not inherit from `StageResult`.

## Consequences

- "Did this unit of work succeed" and "did every required stage succeed" stay separate questions, computed separately.
- Fields that exist only for a whole run never leak into every stage's result type.
- The pipeline result can be built from, and serialized as, the stage results it holds, with no stage-specific code.
- When implemented, `run_pipeline` stops returning `object`, and `main.py` can log or persist the typed result.

## Alternatives considered

- Subclassing `StageResult`: reuses the timing fields, but the pipeline result would have to satisfy the single-stage contract and would force pipeline-only fields onto every stage.
