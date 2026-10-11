# 0003. Ingestion manifest lives in the run's artifact directory

- Status: Accepted
- Date: 2026-10

## Context

`IngestionManifest` is an append-only JSONL log with one entry per ingestion attempt (verified, corrupt, or failed). It needs a path. Options: derive it from the run's artifact directory, add a field for it in `ArtifactsConfig`, or use a fixed shared location outside the run folder.

## Decision

`pipeline.py` builds `manifest_path = context.artifact_dir / "ingestion_manifest.jsonl"`. Each run gets its own manifest.

## Consequences

- One folder tells the story of a run: config copy, `run_metadata.json`, and the manifest.
- No config schema change and no new way to misconfigure a path; no write contention between runs.
- There is no single cross-run history. If one is wanted, build it by reading the per-run files.
- The filename is hard-coded. Make it configurable only if it actually needs to vary by environment.

## Alternatives considered

- A config field in `ArtifactsConfig`: more flexible, but adds validation and tests for something with one sensible value today.
- A shared, project-wide manifest: suits an audit history across runs, at the cost of per-run provenance.
