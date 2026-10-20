"""Stage 2: schema validation (header contract only, ADR 0008)."""

from dataclasses import dataclass
from enum import Enum


class ViolationCode(str, Enum):
    """The kinds of problem stage 2 can report."""

    MISSING_COLUMN = "missing_column"
    EMPTY_DATASET = "empty_dataset"


@dataclass(frozen=True)
class SchemaViolation:
    """One specific problem found in the dataset.

    `column` names the column the problem is about, or is None when the
    problem concerns the whole dataset (for example, EMPTY_DATASET).
    """

    code: ViolationCode
    column: str | None
    message: str


def check_header_contract(
    required_columns: tuple[str, ...],
    actual_columns: tuple[str, ...],
    row_count: int,
) -> tuple[tuple[SchemaViolation, ...], tuple[str, ...]]:
    """Compares the required columns with the file's actual columns.

    Pure: no file access, logging or clock. Returns (violations, extra_columns).
    Missing columns come in declared order, then EMPTY_DATASET if there are
    no rows, then extras in file order (ADR 0008 §2, §9; F5, F6).
    """
    violations: list[SchemaViolation] = []
    extra_columns: list[str] = []

    # Sets are for lookups only. Output always comes from the tuples.
    actual_names = set(actual_columns)
    required_names = set(required_columns)

    for column in required_columns:
        if column not in actual_names:
            violations.append(
                SchemaViolation(
                    code=ViolationCode.MISSING_COLUMN,
                    column=column,
                    message=f"Required column {column!r} is missing",
                )
            )

    if row_count == 0:
        violations.append(
            SchemaViolation(
                code=ViolationCode.EMPTY_DATASET,
                column=None,
                message="Dataset has no data rows",
            )
        )

    for column in actual_columns:
        if column not in required_names:
            extra_columns.append(column)

    return tuple(violations), tuple(extra_columns)
