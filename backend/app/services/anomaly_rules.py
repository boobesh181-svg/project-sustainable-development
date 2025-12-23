"""Anomaly detection rules: deterministic, explainable fraud detection."""

from math import radians, cos, sin, asin, sqrt
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.anomaly_alert import AnomalyAlert, AnomalySeverity
from app.models.material_token import MaterialToken
from app.models.delivery_verification import DeliveryVerification
from app.models.project import Project


# ---------------------
# Utility: distance (km)
# ---------------------
def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate great-circle distance between two GPS coordinates.
    
    Args:
        lat1, lon1: Origin coordinates (decimal degrees)
        lat2, lon2: Destination coordinates (decimal degrees)
        
    Returns:
        Distance in kilometers
    """
    R = 6371  # Earth radius in kilometers
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return R * c


# ---------------------
# RULE 1 — Excess quantity
# ---------------------
async def rule_excess_quantity(
    db: AsyncSession, token: MaterialToken
) -> AnomalyAlert | None:
    """
    Detect quantity inflation (single token exceeds threshold).
    
    Rules:
    - MAX_QTY = 1000 units per token (configurable)
    - Severity: HIGH (potential over-billing fraud)
    
    Returns:
        AnomalyAlert if quantity > threshold, None otherwise
    """
    MAX_QTY = 1000.0  # Example threshold (adjust per material type)

    if float(token.quantity) > MAX_QTY:
        return AnomalyAlert(
            project_id=token.project_id,
            token_uid=token.token_uid,
            rule_code="EXCESS_QUANTITY",
            severity=AnomalySeverity.HIGH,
            description=f"Token quantity ({token.quantity:.2f} {token.unit}) exceeds allowed threshold",
            numeric_value=float(token.quantity),
            threshold=MAX_QTY,
        )
    return None


# ---------------------
# RULE 2 — Distance anomaly
# ---------------------
async def rule_distance_anomaly(
    db: AsyncSession, project: Project, delivery: DeliveryVerification
) -> AnomalyAlert | None:
    """
    Detect delivery far from project site (GPS mismatch).
    
    Rules:
    - MAX_DISTANCE_KM = 2.0 km from project site (configurable)
    - Severity: HIGH (potential wrong site or fake delivery)
    
    Returns:
        AnomalyAlert if distance > threshold, None otherwise
    """
    MAX_DISTANCE_KM = 2.0  # 2km radius around project site

    # Validate project has GPS coordinates
    if project.lat is None or project.lon is None:
        return None  # Cannot check distance without project GPS

    distance = haversine(
        project.lat, project.lon, delivery.delivery_lat, delivery.delivery_lon
    )

    if distance > MAX_DISTANCE_KM:
        # Fetch material token for token_uid
        result = await db.execute(
            select(MaterialToken).where(
                MaterialToken.id == delivery.material_token_id
            )
        )
        token = result.scalar_one_or_none()
        token_uid = token.token_uid if token else None

        return AnomalyAlert(
            project_id=project.id,
            token_uid=token_uid,
            rule_code="DISTANCE_MISMATCH",
            severity=AnomalySeverity.HIGH,
            description=f"Delivery occurred {distance:.2f} km from project site (max {MAX_DISTANCE_KM} km)",
            numeric_value=distance,
            threshold=MAX_DISTANCE_KM,
        )
    return None


# ---------------------
# RULE 3 — Duplicate photo hash
# ---------------------
async def rule_duplicate_photo(
    db: AsyncSession, delivery: DeliveryVerification
) -> AnomalyAlert | None:
    """
    Detect photo reuse across multiple deliveries (same photo for different tokens).
    
    Rules:
    - Photo fingerprint must be unique per delivery
    - Severity: HIGH (potential fake evidence)
    
    Returns:
        AnomalyAlert if photo fingerprint already exists, None otherwise
    """
    # Check if this photo fingerprint exists in other deliveries
    result = await db.execute(
        select(func.count(DeliveryVerification.id))
        .where(
            DeliveryVerification.photo_fingerprint == delivery.photo_fingerprint,
            DeliveryVerification.id != delivery.id,
        )
    )
    count = result.scalar() or 0

    if count > 0:
        # Fetch material token for token_uid
        result_token = await db.execute(
            select(MaterialToken).where(
                MaterialToken.id == delivery.material_token_id
            )
        )
        token = result_token.scalar_one_or_none()
        token_uid = token.token_uid if token else None

        return AnomalyAlert(
            project_id=token.project_id if token else None,
            token_uid=token_uid,
            rule_code="DUPLICATE_PHOTO",
            severity=AnomalySeverity.HIGH,
            description=f"Delivery photo reused across {count + 1} different tokens (evidence fraud)",
        )
    return None


# ---------------------
# RULE 4 — Suspicious supplier (frequency)
# ---------------------
async def rule_suspicious_supplier(
    db: AsyncSession, token: MaterialToken
) -> AnomalyAlert | None:
    """
    Detect suppliers with excessive deliveries in short time window.
    
    Rules:
    - MAX_TOKENS_PER_DAY = 10 tokens per supplier per day
    - Severity: MEDIUM (potential shell company or token farming)
    
    Returns:
        AnomalyAlert if supplier exceeds threshold, None otherwise
    """
    MAX_TOKENS_PER_DAY = 10

    from datetime import timedelta

    # Count tokens from same supplier in last 24 hours
    result = await db.execute(
        select(func.count(MaterialToken.id))
        .where(
            MaterialToken.supplier_name == token.supplier_name,
            MaterialToken.issued_at >= token.issued_at - timedelta(days=1),
        )
    )
    count = result.scalar() or 0

    if count > MAX_TOKENS_PER_DAY:
        return AnomalyAlert(
            project_id=token.project_id,
            token_uid=token.token_uid,
            rule_code="SUSPICIOUS_SUPPLIER",
            severity=AnomalySeverity.MEDIUM,
            description=f"Supplier '{token.supplier_name}' issued {count} tokens in 24h (max {MAX_TOKENS_PER_DAY})",
            numeric_value=float(count),
            threshold=float(MAX_TOKENS_PER_DAY),
        )
    return None
