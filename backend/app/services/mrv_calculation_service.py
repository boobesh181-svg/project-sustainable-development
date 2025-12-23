"""MRV calculation services that rely solely on snapshotted emission factors.

Key guarantees:
- Never read live emission factors or mutable lookup tables.
- Use only the snapshotted factor fields stored on MRV reports.
- Deterministic outputs via Decimal math; no floating-point drift.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, Tuple

from app.models.mrv_report import MRVReport

# Deterministic quantization (6 decimal places aligns with Numeric(18, 6))
Q = Decimal("0.000001")


def _require_snapshot(report: MRVReport) -> Tuple[Decimal, str, str]:
    """Ensure the report carries a full emission factor snapshot.

    Returns the factor value (Decimal), version, and hash. Raises if missing.
    """
    if (
        report.emission_factor_value_snapshot is None
        or report.emission_factor_version_snapshot is None
        or report.emission_factor_hash_snapshot is None
    ):
        raise ValueError(
            "MRV report is missing emission factor snapshot fields; cannot calculate deterministically"
        )

    return (
        Decimal(str(report.emission_factor_value_snapshot)),
        str(report.emission_factor_version_snapshot),
        str(report.emission_factor_hash_snapshot),
    )


def _parse_measurement(value: str) -> Decimal:
    """Parse a measurement value from MRVReport.value deterministically."""
    try:
        return Decimal(str(value))
    except Exception as exc:
        raise ValueError(f"MRV report measurement value is not numeric: {value!r}") from exc


def calculate_report_co2(report: MRVReport) -> dict:
    """Calculate CO2 for a single MRV report using its snapshotted emission factor.

    - Uses only snapshotted fields (value/version/hash) stored on the report.
    - Deterministic Decimal math.
    """
    factor_value, factor_version, factor_hash = _require_snapshot(report)
    measurement = _parse_measurement(report.value)

    co2e = (measurement * factor_value).quantize(Q, rounding=ROUND_HALF_UP)

    return {
        "report_id": str(report.id),
        "co2e": co2e,
        "co2e_unit": "kg_co2e",  # assumed unit for factor snapshot
        "factor_version": factor_version,
        "factor_hash": factor_hash,
        "factor_value": factor_value.quantize(Q, rounding=ROUND_HALF_UP),
        "input_value": measurement.quantize(Q, rounding=ROUND_HALF_UP),
    }


def aggregate_reports_co2(reports: Iterable[MRVReport]) -> dict:
    """Aggregate deterministic CO2 across multiple reports (snapshot-only).

    Returns total and per-report breakdown; never touches live factors.
    """
    breakdown = []
    total = Decimal("0")

    for report in reports:
        result = calculate_report_co2(report)
        total += result["co2e"]
        breakdown.append(result)

    total = total.quantize(Q, rounding=ROUND_HALF_UP)

    return {
        "total_co2e": total,
        "co2e_unit": "kg_co2e",
        "reports": breakdown,
    }
