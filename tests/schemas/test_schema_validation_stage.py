"""Tests for src.schemas.schema_validation_stage: check_header_contract."""

import pytest

from src.schemas.schema_validation_stage import (
    SchemaViolation,
    ViolationCode,
    check_header_contract,
)

REQUIRED = ("tenure", "customerID", "Churn")


def pairs(
    violations: tuple[SchemaViolation, ...],
) -> tuple[tuple[ViolationCode, str | None], ...]:
    """Reduces violations to (code, column), so tests ignore message wording."""
    return tuple((v.code, v.column) for v in violations)


class TestPassingCases:
    @pytest.mark.parametrize(
        ("actual", "expected_extras"),
        [
            (("tenure", "customerID", "Churn"), ()),  # exact match
            (("Churn", "customerID", "tenure"), ()),  # reordered: order is ignored
            (
                ("tenure", "zeta", "customerID", "alpha", "Churn"),
                ("zeta", "alpha"),  # extras keep file order, not sorted
            ),
        ],
    )
    def test_no_violations(
        self, actual: tuple[str, ...], expected_extras: tuple[str, ...]
    ) -> None:
        violations, extras = check_header_contract(REQUIRED, actual, row_count=10)

        assert violations == ()
        assert extras == expected_extras


class TestMissingColumns:
    def test_missing_columns_come_in_declared_order(self) -> None:
        # Declared order is tenure, customerID. Alphabetical would flip them.
        violations, extras = check_header_contract(REQUIRED, ("Churn",), row_count=10)

        assert pairs(violations) == (
            (ViolationCode.MISSING_COLUMN, "tenure"),
            (ViolationCode.MISSING_COLUMN, "customerID"),
        )
        assert extras == ()

    def test_case_variant_is_missing_and_extra(self) -> None:
        violations, extras = check_header_contract(
            REQUIRED, ("tenure", "customerid", "Churn"), row_count=10
        )

        assert pairs(violations) == ((ViolationCode.MISSING_COLUMN, "customerID"),)
        assert extras == ("customerid",)

    def test_whitespace_padded_name_is_missing_and_extra(self) -> None:
        violations, extras = check_header_contract(
            REQUIRED, ("tenure", "customerID", "Churn "), row_count=10
        )

        assert pairs(violations) == ((ViolationCode.MISSING_COLUMN, "Churn"),)
        assert extras == ("Churn ",)

    def test_message_names_the_missing_column(self) -> None:
        violations, _ = check_header_contract(
            REQUIRED, ("customerID", "Churn"), row_count=10
        )

        assert "tenure" in violations[0].message


class TestEmptyDataset:
    def test_header_only_file_reports_only_empty_dataset(self) -> None:
        violations, extras = check_header_contract(REQUIRED, REQUIRED, row_count=0)

        assert pairs(violations) == ((ViolationCode.EMPTY_DATASET, None),)
        assert extras == ()

    def test_zero_byte_file_reports_every_missing_column_then_empty(self) -> None:
        violations, extras = check_header_contract(REQUIRED, (), row_count=0)

        assert pairs(violations) == (
            (ViolationCode.MISSING_COLUMN, "tenure"),
            (ViolationCode.MISSING_COLUMN, "customerID"),
            (ViolationCode.MISSING_COLUMN, "Churn"),
            (ViolationCode.EMPTY_DATASET, None),
        )
        assert extras == ()

    def test_missing_empty_and_extras_are_all_reported_together(self) -> None:
        violations, extras = check_header_contract(
            REQUIRED, ("customerID", "extra"), row_count=0
        )

        assert pairs(violations) == (
            (ViolationCode.MISSING_COLUMN, "tenure"),
            (ViolationCode.MISSING_COLUMN, "Churn"),
            (ViolationCode.EMPTY_DATASET, None),
        )
        assert extras == ("extra",)


class TestKnownLimits:
    """These lock in accepted limits of the thin version, so changing them
    later is a deliberate decision and not an accident."""

    def test_bom_prefixed_name_is_missing_and_extra(self) -> None:
        # F3: BOM handling is deferred, so a leading BOM breaks exact matching.
        violations, extras = check_header_contract(
            REQUIRED, ("tenure", "\ufeffcustomerID", "Churn"), row_count=10
        )

        assert pairs(violations) == ((ViolationCode.MISSING_COLUMN, "customerID"),)
        assert extras == ("\ufeffcustomerID",)

    def test_duplicate_extra_columns_are_listed_twice(self) -> None:
        # F6: duplicate header checks are deferred.
        _, extras = check_header_contract(REQUIRED, REQUIRED + ("x", "x"), row_count=10)

        assert extras == ("x", "x")
