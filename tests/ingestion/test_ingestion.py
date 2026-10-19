"""Tests for src.ingestion.ingestion: run (single item)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.core.types import StageFailed, StageStatus
from src.ingestion.ingestion import (
    IngestionItem,
    IngestionResult,
    IngestionStageFailed,
    run,
)
from src.ingestion.manifest import IngestionManifest


def read_manifest_entries(manifest_path: Path) -> list[dict]:
    if not manifest_path.exists():
        return []
    return [json.loads(line) for line in manifest_path.read_text().splitlines()]


def make_item(name: str, expected_sha256: str = "MATCH") -> IngestionItem:
    return IngestionItem(
        url=f"https://example.com/{name}",
        filename=name,
        expected_sha256=expected_sha256,
    )


# ─────────────────────────────────────────────────────────────────
# Manifest construction failure (before any item work starts)
# ─────────────────────────────────────────────────────────────────


class TestManifestConstructionFailure:
    def test_manifest_parent_path_is_a_file_raises_not_a_directory_error(
        self, tmp_path: Path
    ) -> None:
        # If manifest_path's parent already exists as a plain file (not
        # a directory), IngestionManifest's own ensure_dir_exists call
        # raises NotADirectoryError. This happens before any item is
        # attempted, so no IngestionResult is ever produced — confirms
        # this fails loudly rather than silently.
        blocking_file = tmp_path / "not_a_directory"
        blocking_file.write_text("i am a file, not a directory")
        manifest_path = blocking_file / "manifest.jsonl"

        with pytest.raises(NotADirectoryError):
            run(make_item("data.zip"), manifest_path)


# ─────────────────────────────────────────────────────────────────
# Single item — success / corrupt / failure
# ─────────────────────────────────────────────────────────────────


class TestSingleItemOutcomes:
    @patch("src.ingestion.ingestion.get_raw_data_path")
    @patch("src.ingestion.ingestion.calculate_sha256")
    @patch("src.ingestion.ingestion.download_stream")
    def test_success_writes_verified_entry_and_returns_no_failure(
        self,
        mock_download: MagicMock,
        mock_hash: MagicMock,
        mock_path: MagicMock,
        tmp_path: Path,
    ) -> None:
        output_file = tmp_path / "data.zip"
        output_file.write_bytes(b"real content")
        mock_path.return_value = output_file
        mock_hash.return_value = "MATCH"

        item = make_item("data.zip", "MATCH")
        manifest_path = tmp_path / "manifest.jsonl"

        result = run(item, manifest_path)

        assert len(result.succeeded) == 1
        assert result.failed == []
        assert result.succeeded[0].status == "verified"
        mock_download.assert_called_once()

        entries = read_manifest_entries(manifest_path)
        assert entries[0]["status"] == "verified"
        assert entries[0]["sha256"] == "MATCH"

    @patch("src.ingestion.ingestion.get_raw_data_path")
    @patch("src.ingestion.ingestion.calculate_sha256")
    @patch("src.ingestion.ingestion.download_stream")
    def test_hash_mismatch_writes_corrupt_entry_and_raises(
        self,
        mock_download: MagicMock,
        mock_hash: MagicMock,
        mock_path: MagicMock,
        tmp_path: Path,
    ) -> None:
        output_file = tmp_path / "data.zip"
        output_file.write_bytes(b"wrong content")
        mock_path.return_value = output_file
        mock_hash.return_value = "ACTUAL_HASH"

        item = make_item("data.zip", "EXPECTED_HASH")
        manifest_path = tmp_path / "manifest.jsonl"

        with pytest.raises(IngestionStageFailed, match="1 of 1"):
            run(item, manifest_path)

        entries = read_manifest_entries(manifest_path)
        assert entries[0]["status"] == "corrupt"
        assert entries[0]["sha256"] == "ACTUAL_HASH"
        assert entries[0]["expected_hash"] == "EXPECTED_HASH"

    @patch("src.ingestion.ingestion.get_raw_data_path")
    @patch("src.ingestion.ingestion.calculate_sha256")
    @patch("src.ingestion.ingestion.download_stream")
    def test_hash_match_with_different_case_is_treated_as_verified(
        self,
        mock_download: MagicMock,
        mock_hash: MagicMock,
        mock_path: MagicMock,
        tmp_path: Path,
    ) -> None:
        # actual and expected hashes are compared case-insensitively. A
        # hash that matches except for letter case is a genuine match,
        # not corruption.
        output_file = tmp_path / "data.zip"
        output_file.write_bytes(b"real content")
        mock_path.return_value = output_file
        mock_hash.return_value = "abcdef0123"

        item = make_item("data.zip", "ABCDEF0123")
        manifest_path = tmp_path / "manifest.jsonl"

        result = run(item, manifest_path)  # must not raise

        assert result.succeeded[0].status == "verified"
        entries = read_manifest_entries(manifest_path)
        assert entries[0]["status"] == "verified"
        assert result.verified_file is not None
        assert result.verified_file.sha256 == "abcdef0123"

    @patch("src.ingestion.ingestion.get_raw_data_path")
    @patch("src.ingestion.ingestion.download_stream")
    def test_download_failure_writes_failed_entry_and_raises(
        self, mock_download: MagicMock, mock_path: MagicMock, tmp_path: Path
    ) -> None:
        output_file = tmp_path / "data.zip"
        mock_path.return_value = output_file
        mock_download.side_effect = ConnectionError("network unreachable")

        item = make_item("data.zip")
        manifest_path = tmp_path / "manifest.jsonl"

        with pytest.raises(IngestionStageFailed, match="1 of 1"):
            run(item, manifest_path)

        entries = read_manifest_entries(manifest_path)
        assert entries[0]["status"] == "failed"
        assert entries[0]["error"] == "network unreachable"

    @patch("src.ingestion.ingestion.get_raw_data_path")
    @patch("src.ingestion.ingestion.download_stream")
    def test_missing_output_file_after_download_raises_file_not_found(
        self, mock_download: MagicMock, mock_path: MagicMock, tmp_path: Path
    ) -> None:
        # download_stream is mocked to a no-op, so output_path is never
        # actually created. calculate_sha256 (unmocked here) then tries
        # to open a file that doesn't exist — caught by _ingest_one_item's
        # broad except, same as any other failure.
        output_file = tmp_path / "data.zip"  # never created
        mock_path.return_value = output_file
        mock_download.return_value = None

        item = make_item("data.zip")
        manifest_path = tmp_path / "manifest.jsonl"

        with pytest.raises(IngestionStageFailed, match="1 of 1"):
            run(item, manifest_path)

        entries = read_manifest_entries(manifest_path)
        assert entries[0]["status"] == "failed"

    @patch("src.ingestion.ingestion.get_raw_data_path")
    def test_path_traversal_in_filename_is_treated_as_item_failure(
        self, mock_path: MagicMock, tmp_path: Path
    ) -> None:
        # get_raw_data_path's own guard raises ValueError — confirm it's
        # caught and recorded like any other failure, not left to crash.
        mock_path.side_effect = ValueError("filename escapes the raw data directory")

        item = make_item("../../etc/passwd")
        manifest_path = tmp_path / "manifest.jsonl"

        with pytest.raises(IngestionStageFailed, match="1 of 1"):
            run(item, manifest_path)

        entries = read_manifest_entries(manifest_path)
        assert len(entries) == 1
        assert entries[0]["status"] == "failed"
        assert "escapes the raw data directory" in entries[0]["error"]

    @patch("src.ingestion.ingestion.get_raw_data_path")
    @patch("src.ingestion.ingestion.calculate_sha256")
    @patch("src.ingestion.ingestion.download_stream")
    def test_verified_run_exposes_facts_about_the_saved_file(
        self,
        mock_download: MagicMock,
        mock_hash: MagicMock,
        mock_path: MagicMock,
        tmp_path: Path,
    ) -> None:
        content = b"real content"
        output_file = tmp_path / "data.zip"
        output_file.write_bytes(content)
        mock_path.return_value = output_file
        mock_hash.return_value = "MATCH"

        result = run(make_item("data.zip", "MATCH"), tmp_path / "manifest.jsonl")

        assert result.verified_file is not None
        assert result.verified_file.path == output_file
        assert result.verified_file.sha256 == "MATCH"
        assert result.verified_file.size_bytes == len(content)

    @patch("src.ingestion.ingestion.get_raw_data_path")
    @patch("src.ingestion.ingestion.calculate_sha256")
    @patch("src.ingestion.ingestion.download_stream")
    def test_corrupt_file_has_no_verified_file(
        self,
        mock_download: MagicMock,
        mock_hash: MagicMock,
        mock_path: MagicMock,
        tmp_path: Path,
    ) -> None:
        output_file = tmp_path / "data.zip"
        output_file.write_bytes(b"wrong content")
        mock_path.return_value = output_file
        mock_hash.return_value = "ACTUAL_HASH"

        with pytest.raises(IngestionStageFailed) as exc_info:
            run(make_item("data.zip", "EXPECTED_HASH"), tmp_path / "manifest.jsonl")

        assert exc_info.value.result.verified_file is None

    @patch("src.ingestion.ingestion.get_raw_data_path")
    @patch("src.ingestion.ingestion.download_stream")
    def test_failed_download_has_no_verified_file(
        self, mock_download: MagicMock, mock_path: MagicMock, tmp_path: Path
    ) -> None:
        mock_path.return_value = tmp_path / "data.zip"
        mock_download.side_effect = ConnectionError("network unreachable")

        with pytest.raises(IngestionStageFailed) as exc_info:
            run(make_item("data.zip"), tmp_path / "manifest.jsonl")

        assert exc_info.value.result.verified_file is None


# ─────────────────────────────────────────────────────────────────
# Failure before a manifest run exists
# ─────────────────────────────────────────────────────────────────


class TestFailureBeforeRunStarts:
    def test_start_run_failure_is_recorded_as_failed_item_with_unset_run_id(
        self, tmp_path: Path, caplog: MagicMock
    ) -> None:
        # If manifest.start_run itself fails, no manifest entry was ever
        # opened, so there is nothing to attach the failure to. The item
        # is reported as failed with run_id "unset" and the error is
        # logged instead.
        manifest_path = tmp_path / "manifest.jsonl"

        with (
            patch.object(
                IngestionManifest,
                "start_run",
                side_effect=OSError("cannot open manifest"),
            ),
            caplog.at_level("ERROR"),
            pytest.raises(IngestionStageFailed) as exc_info,
        ):
            run(make_item("data.zip"), manifest_path)

        failed = exc_info.value.result.failed[0]
        assert failed.run_id == "unset"
        assert failed.error == "cannot open manifest"
        assert "cannot open manifest" in caplog.text
        assert read_manifest_entries(manifest_path) == []


# ─────────────────────────────────────────────────────────────────
# StageResult fields — stage_name, status, timestamps, duration
# ─────────────────────────────────────────────────────────────────


class TestStageResultFields:
    @patch("src.ingestion.ingestion.get_raw_data_path")
    @patch("src.ingestion.ingestion.calculate_sha256")
    @patch("src.ingestion.ingestion.download_stream")
    def test_successful_run_reports_success_status_and_stage_name(
        self,
        mock_download: MagicMock,
        mock_hash: MagicMock,
        mock_path: MagicMock,
        tmp_path: Path,
    ) -> None:
        def fake_path(filename: str) -> Path:
            path = tmp_path / filename
            path.write_bytes(b"content")
            return path

        mock_path.side_effect = fake_path
        mock_hash.return_value = "MATCH"

        item = make_item("a.zip")
        manifest_path = tmp_path / "manifest.jsonl"

        result = run(item, manifest_path)

        assert result.stage_name == "ingestion"
        assert result.status == StageStatus.SUCCESS

    @patch("src.ingestion.ingestion.get_raw_data_path")
    @patch("src.ingestion.ingestion.calculate_sha256")
    @patch("src.ingestion.ingestion.download_stream")
    def test_successful_run_has_sane_timestamps_and_duration(
        self,
        mock_download: MagicMock,
        mock_hash: MagicMock,
        mock_path: MagicMock,
        tmp_path: Path,
    ) -> None:
        def fake_path(filename: str) -> Path:
            path = tmp_path / filename
            path.write_bytes(b"content")
            return path

        mock_path.side_effect = fake_path
        mock_hash.return_value = "MATCH"

        item = make_item("a.zip")
        manifest_path = tmp_path / "manifest.jsonl"

        result = run(item, manifest_path)

        assert result.duration_seconds >= 0
        assert result.completed_at >= result.started_at

    @patch("src.ingestion.ingestion.get_raw_data_path")
    @patch("src.ingestion.ingestion.download_stream")
    def test_failed_run_reports_failed_status(
        self, mock_download: MagicMock, mock_path: MagicMock, tmp_path: Path
    ) -> None:
        output_file = tmp_path / "data.zip"
        mock_path.return_value = output_file
        mock_download.side_effect = ConnectionError("network unreachable")

        item = make_item("data.zip")
        manifest_path = tmp_path / "manifest.jsonl"

        with pytest.raises(IngestionStageFailed) as exc_info:
            run(item, manifest_path)

        assert exc_info.value.result.status == StageStatus.FAILED
        assert exc_info.value.result.stage_name == "ingestion"


# ─────────────────────────────────────────────────────────────────
# IngestionStageFailed.result — the exception carries the finalized result
# ─────────────────────────────────────────────────────────────────


class TestIngestionStageFailedResult:
    @patch("src.ingestion.ingestion.get_raw_data_path")
    @patch("src.ingestion.ingestion.download_stream")
    def test_result_is_a_real_ingestion_result_instance(
        self, mock_download: MagicMock, mock_path: MagicMock, tmp_path: Path
    ) -> None:
        output_file = tmp_path / "data.zip"
        mock_path.return_value = output_file
        mock_download.side_effect = ConnectionError("network unreachable")

        item = make_item("data.zip")
        manifest_path = tmp_path / "manifest.jsonl"

        with pytest.raises(IngestionStageFailed) as exc_info:
            run(item, manifest_path)

        assert isinstance(exc_info.value.result, IngestionResult)

    @patch("src.ingestion.ingestion.get_raw_data_path")
    @patch("src.ingestion.ingestion.download_stream")
    def test_exception_is_a_stage_failed(
        self, mock_download: MagicMock, mock_path: MagicMock, tmp_path: Path
    ) -> None:
        mock_path.return_value = tmp_path / "data.zip"
        mock_download.side_effect = ConnectionError("network unreachable")

        with pytest.raises(StageFailed) as exc_info:
            run(make_item("data.zip"), tmp_path / "manifest.jsonl")

        assert isinstance(exc_info.value, IngestionStageFailed)
        assert exc_info.value.result.stage_name == "ingestion"


# ─────────────────────────────────────────────────────────────────
# The "manifest logging itself fails" fallback
# ─────────────────────────────────────────────────────────────────


class TestManifestLoggingFailureFallback:
    @patch("src.ingestion.ingestion.get_raw_data_path")
    @patch("src.ingestion.ingestion.download_stream")
    def test_does_not_crash_or_mask_original_error_when_manifest_write_also_fails(
        self,
        mock_download: MagicMock,
        mock_path: MagicMock,
        tmp_path: Path,
        caplog: MagicMock,
    ) -> None:
        output_file = tmp_path / "data.zip"
        mock_path.return_value = output_file
        mock_download.side_effect = ConnectionError("network unreachable")

        item = make_item("data.zip")
        manifest_path = tmp_path / "manifest.jsonl"

        with (
            patch.object(
                IngestionManifest, "log_failure", side_effect=OSError("disk full")
            ),
            caplog.at_level("CRITICAL"),
            pytest.raises(IngestionStageFailed),
        ):
            run(item, manifest_path)

        # the original ConnectionError must not leak out in place of
        # IngestionStageFailed, and the failure must still be visible
        # via the logging fallback
        assert "network unreachable" in caplog.text
