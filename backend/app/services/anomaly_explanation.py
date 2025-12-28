"""Anomaly explanation engine (deterministic, non-ML).

Module 4 goal:
- Provide clear "why flagged" explanations
- Identify which rule triggered
- Provide confidence level
- Suggest next action

We keep this deterministic: same inputs -> same output.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.anomaly_alert import AnomalyAlert, AnomalySeverity


@dataclass(frozen=True)
class ExplanationResult:
    rule_id: str
    explanation: str
    requires_action: bool


_RULE_CONFIDENCE: dict[str, str] = {
    "EXCESS_QUANTITY": "High",
    "DISTANCE_MISMATCH": "High",
    "DUPLICATE_PHOTO": "High",
    "SUSPICIOUS_SUPPLIER": "Medium",
}

_RULE_NEXT_ACTION: dict[str, str] = {
    "EXCESS_QUANTITY": "Verify invoice/BOQ quantity and token issuance authorization.",
    "DISTANCE_MISMATCH": "Verify GPS/photo evidence and confirm delivery address matches the project.",
    "DUPLICATE_PHOTO": "Request fresh photo evidence and check for evidence reuse across tokens.",
    "SUSPICIOUS_SUPPLIER": "Review supplier activity for abnormal issuance frequency and validate supporting docs.",
}


def _fmt_num(value: object) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.2f}"
    except Exception:
        return str(value)


def build_anomaly_explanation(alert: AnomalyAlert) -> ExplanationResult:
    """Build explanation metadata for an anomaly alert.

    Note: We do not mutate or write to DB here; callers can persist if needed.
    """

    rule_id = alert.rule_id or alert.rule_code

    # Deterministic default: HIGH => requires action
    requires_action = bool(alert.severity == AnomalySeverity.HIGH)

    confidence = _RULE_CONFIDENCE.get(alert.rule_code, "Medium")
    next_action = _RULE_NEXT_ACTION.get(alert.rule_code, "Review evidence and validate source records.")

    main: str
    if alert.rule_code == "EXCESS_QUANTITY" and alert.numeric_value is not None and alert.threshold is not None:
        main = (
            f"Quantity is {_fmt_num(alert.numeric_value)} (threshold {_fmt_num(alert.threshold)})."
        )
    elif (
        alert.rule_code == "DISTANCE_MISMATCH"
        and alert.numeric_value is not None
        and alert.threshold is not None
    ):
        main = (
            f"Delivery occurred {_fmt_num(alert.numeric_value)} km from the project site "
            f"(threshold {_fmt_num(alert.threshold)} km)."
        )
    elif (
        alert.rule_code == "SUSPICIOUS_SUPPLIER"
        and alert.numeric_value is not None
        and alert.threshold is not None
    ):
        main = (
            f"Supplier issued {_fmt_num(alert.numeric_value)} tokens in 24h "
            f"(threshold {_fmt_num(alert.threshold)})."
        )
    else:
        # Fallback to existing description for any rule (incl. DUPLICATE_PHOTO)
        main = alert.description

    explanation = f"{main} Confidence: {confidence}. Suggested next action: {next_action}"

    return ExplanationResult(rule_id=rule_id, explanation=explanation, requires_action=requires_action)


def apply_explanation_defaults(alert: AnomalyAlert) -> None:
    """Populate rule_id/explanation/requires_action if missing.

    This is safe to call on existing DB rows where these columns were added later.
    """

    result = build_anomaly_explanation(alert)

    if not getattr(alert, "rule_id", None):
        alert.rule_id = result.rule_id
    if not getattr(alert, "explanation", None):
        alert.explanation = result.explanation

    # requires_action is non-nullable; keep existing value if explicitly set.
    if getattr(alert, "requires_action", None) is False and result.requires_action:
        alert.requires_action = True
