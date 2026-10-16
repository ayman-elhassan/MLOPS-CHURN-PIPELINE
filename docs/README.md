# Decision records

One file per decision that a future reader (human or AI assistant) could not safely infer from the code.

## When to write one

Write an ADR if, seeing only the code, someone could plausibly undo or violate the decision. Skip it if a code comment or a test name already makes the decision hard to miss.

## Format

File name: `NNNN-short-title.md`, numbered in order. Match the existing records:

```
# NNNN. Title

- Status: Proposed | Accepted | Accepted (temporary: <removal condition>) | Deferred | Superseded
- Date: YYYY-MM
- Supersedes: NNNN            (omit if none)
- Superseded by: NNNN         (add to the OLD record when replaced)

## Context
## Decision
## Consequences
## Alternatives considered
```

## Rules

- Do not rewrite an accepted record to change its meaning. To change a decision, write a new ADR with `Supersedes`, then add `Superseded by` and set `Status: Superseded` on the old one. Marking a flagged item as confirmed or adjusting an unbuilt detail may be edited in place with a note.
- Temporary decisions state their removal condition in `Status`.
- Update the table in `docs/PROJECT_CONTEXT.md` when adding one.

## Index

| # | Title | Status |
|---|---|---|
| 0001 | Ingestion takes a single typed item | Accepted |
| 0002 | `StageFailed` base exception and exit code 3 | Accepted (meaning of 3 clarified in 0009) |
| 0003 | Ingestion manifest lives in the run's artifact directory | Accepted |
| 0004 | A partial pipeline fails loudly | Accepted (temporary) |
| 0005 | A stage failure stops the run | Accepted |
| 0006 | The pipeline-level result composes stage results | Accepted (not yet implemented) |
| 0007 | Stage handoff and shared contracts | Accepted; one provisional item |
| 0008 | Stage 2 scope and policy | Accepted; some items flagged |
| 0009 | Exit code 3 is stage-defined; the run record is deferred | Accepted (exit 3); run record deferred |
