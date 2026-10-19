"""Ingestion stage orchestrator.

Sequences the ingestion flow for one item: resolve a destination path,
download, hash, verify against an expected hash, and record the outcome
in the manifest. Failures are recorded and then surfaced as a single
IngestionStageFailed exception carrying the finalized IngestionResult.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

from src.core.types import StageFailed, StageResult, StageStatus
from src.ingestion.manifest import IngestionManifest
from src.storage.storage import get_raw_data_path
from src.utils.ingest import calculate_sha256, download_stream

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IngestionItem:
    """Everything ingestion needs to fetch and verify one file.

    Owned by ingestion: the orchestrator adapts the outside world into this
    shape, not the other way around.
    """

    url: str
    filename: str
    expected_sha256: str


class IngestionStageFailed(StageFailed):
    """Raised after the ingestion run if the item failed or came back
    corrupt. The failure is already recorded in the manifest; this is the
    stage-level signal that something needs attention.

    Carries the finalized IngestionResult via .result, so a caller can
    inspect which item succeeded or failed.
    """

    result: "IngestionResult"

    def __init__(self, message: str, result: "IngestionResult"):
        super().__init__(message, result)


@dataclass(frozen=True)
class VerifiedFile:
    """Facts about a raw file whose SHA-256 matched the pinned value.

    Exists only for a verified file, so every field is always filled in.
    """

    path: Path
    sha256: str
    size_bytes: int


@dataclass
class IngestionItemResult:
    """The outcome of ingesting a single configured item."""

    filename: str
    url: str
    run_id: str
    status: str  # "verified" | "corrupt" | "failed"
    error: str | None = None


@dataclass
class IngestionResult(StageResult):
    """The outcome of one full ingestion stage run.

    `verified_file` is set only when the file passed verification, so it is
    None on a failed run.
    """

    succeeded: list[IngestionItemResult] = field(default_factory=list)
    failed: list[IngestionItemResult] = field(default_factory=list)
    verified_file: VerifiedFile | None = None

    @property
    def total(self) -> int:
        return len(self.succeeded) + len(self.failed)


def run(item: IngestionItem, manifest_path: Path) -> IngestionResult:
    """Runs the ingestion stage for one item, recording the outcome in
    the manifest at manifest_path.

    Args:
        item: the file to fetch and verify.
        manifest_path: Path to the manifest JSONL file to log into.

    Returns:
        An IngestionResult describing the verified item.

    Raises:
        IngestionStageFailed: if the item failed or came back corrupt.
            Raised only after the outcome is recorded, and carries the
            finalized IngestionResult via .result.
    """

    # Timing starts here. The typed IngestionItem needs no structural
    # precondition checks, so everything from here on counts as stage work.
    open_stage = StageResult.start("ingestion")

    manifest = IngestionManifest(manifest_path)

    succeeded: list[IngestionItemResult] = []
    failed: list[IngestionItemResult] = []

    item_result, verified_file = _ingest_one_item(item, manifest)
    if item_result.status == "verified":
        succeeded.append(item_result)
    else:
        failed.append(item_result)

    result = open_stage.finish(
        IngestionResult,
        StageStatus.FAILED if failed else StageStatus.SUCCESS,
        succeeded=succeeded,
        failed=failed,
        verified_file=verified_file,
    )

    if result.failed:
        raise IngestionStageFailed(
            f"{len(result.failed)} of {result.total} item(s) failed or were corrupt",
            result=result,
        )

    return result


def _ingest_one_item(
    item: IngestionItem, manifest: IngestionManifest
) -> tuple[IngestionItemResult, VerifiedFile | None]:
    """Downloads, hashes, and verifies the item, recording the outcome
    in the manifest. Never raises — any failure (including
    manifest.start_run() itself) is caught, logged to the manifest where
    possible, and reflected in the returned IngestionItemResult instead,
    so run() can always finalize an IngestionResult and raise
    IngestionStageFailed from it.
    """
    # run_id stays None if start_run itself fails — initialized here so
    # the except block below can tell whether a manifest entry was ever
    # opened at all.
    run_id: str | None = None

    try:
        run_id = manifest.start_run(item.url, Path(item.filename))

        output_path = get_raw_data_path(item.filename)
        download_stream(item.url, output_path)
        actual_hash = calculate_sha256(output_path)
        file_size_bytes = output_path.stat().st_size

        # Compared case-insensitively: hex digests have no case-sensitive
        # meaning (hashlib.hexdigest() always returns lowercase, but a
        # config author may reasonably write an uppercase expected_sha256).
        # Without normalizing, an otherwise-correct file would be
        # falsely marked corrupt purely due to letter casing.

        if actual_hash.lower() == item.expected_sha256.lower():
            manifest.log_success(run_id, actual_hash, file_size_bytes)
            return (
                IngestionItemResult(
                    filename=item.filename,
                    url=item.url,
                    run_id=run_id,
                    status="verified",
                ),
                VerifiedFile(
                    path=output_path,
                    sha256=actual_hash,
                    size_bytes=file_size_bytes,
                ),
            )

        manifest.log_corrupt(run_id, actual_hash, file_size_bytes, item.expected_sha256)
        return (
            IngestionItemResult(
                filename=item.filename, url=item.url, run_id=run_id, status="corrupt"
            ),
            None,
        )

    except Exception as e:
        error_message = str(e)

        if run_id is not None:
            try:
                manifest.log_failure(run_id, error_message)
            except Exception:
                # Logging the failure itself failed (e.g. disk full). Don't
                # let that mask the original error or crash the stage —
                # fall back to plain logging so it's still visible somewhere.
                logger.critical(
                    "Failed to record manifest entry for run_id=%s (original error: %s)",
                    run_id,
                    error_message,
                    exc_info=True,
                )
        else:
            # No run was ever started (manifest.start_run itself failed),
            # so there's no manifest entry to attach this failure to.
            logger.error(
                "Item failed before a run could be started (original error: %s)",
                error_message,
            )

        return (
            IngestionItemResult(
                filename=item.filename,
                url=item.url,
                run_id=run_id or "unset",
                status="failed",
                error=error_message,
            ),
            None,
        )
