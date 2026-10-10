"""Tests for src.pipelines.pipeline: run_pipeline."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.core.types import StageResult, StageStatus
from src.ingestion.ingestion import (
    IngestionItem,
    IngestionResult,
    IngestionStageFailed,
)
from src.pipelines.pipeline import run_pipeline


def make_config() -> SimpleNamespace:
    return SimpleNamespace(
        dataset=SimpleNamespace(
            url="https://example.com/data.csv",
            filename="data.csv",
            expected_sha256="abc123",
        )
    )


def make_context(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(artifact_dir=tmp_path)


@patch("src.pipelines.pipeline.run_ingestion")
def test_run_pipeline_calls_ingestion_with_adapted_item_and_manifest_path(
    mock_ingestion: MagicMock, tmp_path: Path
) -> None:
    with pytest.raises(NotImplementedError):
        run_pipeline(make_config(), make_context(tmp_path))  # type: ignore[arg-type]

    mock_ingestion.assert_called_once_with(
        IngestionItem(
            url="https://example.com/data.csv",
            filename="data.csv",
            expected_sha256="abc123",
        ),
        tmp_path / "ingestion_manifest.jsonl",
    )


@patch("src.pipelines.pipeline.run_ingestion")
def test_run_pipeline_propagates_ingestion_failure(
    mock_ingestion: MagicMock, tmp_path: Path
) -> None:
    result = StageResult.start("ingestion").finish(IngestionResult, StageStatus.FAILED)
    mock_ingestion.side_effect = IngestionStageFailed("1 of 1 failed", result)

    with pytest.raises(IngestionStageFailed):
        run_pipeline(make_config(), make_context(tmp_path))  # type: ignore[arg-type]


@patch("src.pipelines.pipeline.run_ingestion", new=MagicMock())
def test_run_pipeline_marks_later_stages_unimplemented(tmp_path: Path) -> None:
    with pytest.raises(NotImplementedError, match="after ingestion"):
        run_pipeline(make_config(), make_context(tmp_path))  # type: ignore[arg-type]
