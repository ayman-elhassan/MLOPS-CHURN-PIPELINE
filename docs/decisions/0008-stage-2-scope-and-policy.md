# 0008. Stage 2 checks the header contract only; tolerant of extra columns; one reader

- Status: Accepted. Items marked [flagged] are approved defaults to be re-reviewed in the stage 2 chat before the step that depends on them.
- Date: 2026-10

## Context

- The raw file is pinned by SHA-256, so its bytes cannot change without a config edit. Stage 2's real value is catching a mismatch between the config and the file (for example after a dataset swap) and publishing the first table-level contract.
- The Telco file has 21 columns, no BOM, no trailing blank row, and 11 blank `TotalCharges` values. `pipeline.yaml` currently requires only `customerID` and `Churn`.
- `build_dataset_ref` reads with plain utf-8, counts a blank trailing line as a row, and scans the whole file.

## Decision

1. Scope: header-level checks only. Row-level work (row width, types, nulls, uniqueness, value domains) belongs to stage 3.
2. Checks in the thin version: every required column is present (violation `MISSING_COLUMN`); the dataset is non-empty, meaning `row_count == 0` (violation `EMPTY_DATASET`). Both checks are always collected, with no gating.
3. Policy: names match exactly (case-sensitive, no trimming); column order is ignored; extra columns are allowed and recorded in `extra_columns`; a missing required column fails.
4. `required_columns` is the complete list of columns the pipeline depends on (all 21, names only). The config validators reject a target that is not in the list and duplicate names (exit code 2). [flagged]
5. Rule for stage 5: features are selected by explicit name from `required_columns`; extra columns never become features implicitly. The allowlist field is designed with stage 5 as a subset of `required_columns`.
6. Value-level invariants (for example `customerID` unique, `Churn` in an allowed set) are declared in config next to the schema and enforced generically in stage 3, not hard-coded to Telco and not in stage 2.
7. One reader: stage 2 reads the file only through `build_dataset_ref`. It never opens the file itself. [flagged]
8. Accepted limits of the thin version: plain utf-8 (no BOM handling), a blank trailing line counts as a row, decode and csv errors propagate (exit 1), and the stage costs O(file) because the ref needs the row count. [flagged]
9. Determinism: never iterate a set to produce output. Missing columns come out in `required_columns` order, extra columns in file header order, violations by check order then column order. Results hold tuples; serialized records use sorted keys. [flagged]
10. Hash use: stage 2 validates by set comparison and records `columns` and `schema_hash` as a baseline. It does not compare the hash with anything. A comparer (against a committed baseline, not by scanning old runs) is built when the byte pin is relaxed, runs are scheduled, or a second dataset appears. [flagged]
11. A 0-byte file yields one `MISSING_COLUMN` per required column (declared order), then `EMPTY_DATASET`. [flagged]
12. The schema block stays in `pipeline.yaml`; models stay in `main.py` for now. Later options, in order: move the models to `src/config/`; a separate schema file when per-column attributes (types, nullability) or a second dataset appear; an Open Data Contract Standard file as a post-project feature.

## Consequences

- A file missing a needed column fails in stage 2 with a precise message instead of failing later.
- The config list must be kept in sync with the columns later stages use.
- Boundary-locking tests: a ragged row and a non-numeric or blank value in a numeric-looking column must pass stage 2 (stage 3 owns them).
- Deferred to one deliberate change of the shared helper (see backlog): `utf-8-sig`, skip blank rows when counting, translate decode and csv errors into an `UNREADABLE` violation. That change updates a pinned test and gets its own ADR.
- Deferred: duplicate and blank header labels, gate-then-collect, near-match hints.

## Alternatives considered

- Strict exact column match: safest for frozen data, breaks on harmless additions and defeats the purpose of a required list.
- Stage-owned header reader plus `build_dataset_ref`: two decoders and two reads; for a BOM file the validated names and the recorded hash would disagree.
- pandas for the header: renames duplicate headers (`a` becomes `a.1`) and is a heavy dependency.
- Pinning an expected schema hash in config: redundant with the file hash and one-way, so it cannot say what changed.
- Comparing with the previous run now: the byte pin makes it compare equal every time, and it needs run-history scanning.
- Putting types and value rules in stage 2: needs a full scan and new config fields before stage 3 is designed.
