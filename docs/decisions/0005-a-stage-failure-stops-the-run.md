# 0005. A stage failure stops the run

- Status: Accepted
- Date: 2026-10

## Context

The pipeline will have eleven sequential stages, each consuming the previous one's output. If stage N ran but did not succeed, the orchestrator must either stop or continue with later stages. Today this is invisible in code: `run_pipeline` has no `try/except` around the ingestion call, so a `StageFailed` simply propagates. Without a recorded decision, a later change could add a "continue anyway" wrapper without anyone noticing it reverses a design choice.

## Decision

`run_pipeline` runs stages in a fixed order and stops at the first stage that raises `StageFailed`. The exception propagates to `main.py`, which logs it and returns exit code 3 (ADR 0002). No later stage runs on the output of a failed one. There is no continue-on-failure mode.

## Consequences

- A failed stage can never feed a plausible-looking but wrong result into feature engineering or training.
- `pipeline.py` stays free of per-stage error handling; adding a stage means adding one call in order.
- A run reports only the first failure. Failures in later stages are not discovered until the earlier one is fixed.
- Anything partial that a stage already wrote (manifest lines, files under `data/raw/`) stays on disk; the stage's own result and the manifest are the record.

## Alternatives considered

- Fail-soft (run every stage, collect all failures): shows more problems per run, but downstream stages would operate on known-bad input and could produce misleading output.
- A per-stage `required` flag: needed only if independent or optional stages appear. Revisit then, as a new ADR that supersedes this one.
