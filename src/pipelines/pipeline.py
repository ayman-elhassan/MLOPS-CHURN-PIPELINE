"""Pipeline orchestration.

Stage implementations will be added incrementally. Keeping their ordering
here gives ``main.py`` one stable delegation point and makes the intended v1
workflow explicit.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.ingestion.ingestion import IngestionItem
from src.ingestion.ingestion import run as run_ingestion

if TYPE_CHECKING:
    from main import PipelineConfig, RunContext


def run_pipeline(config: PipelineConfig, context: RunContext) -> object:
    """Run the v1 churn training workflow.

    Implemented so far: ingestion. Remaining order: schema validation ->
    data quality -> processing -> feature engineering -> splitting ->
    training -> evaluation.

    Raises:
        StageFailed: if a stage ran but did not succeed (for example,
            IngestionStageFailed).
        NotImplementedError: until every stage exists, so a partial run can
            never be mistaken for a complete one.
    """
    # The one place that knows both shapes: config's DatasetConfig on one
    # side, ingestion's own IngestionItem on the other.
    item = IngestionItem(
        url=str(config.dataset.url),
        filename=config.dataset.filename,
        expected_sha256=config.dataset.expected_sha256,
    )
    manifest_path = context.artifact_dir / "ingestion_manifest.jsonl"
    run_ingestion(item, manifest_path)

    raise NotImplementedError("Stages after ingestion have not been implemented yet.")
