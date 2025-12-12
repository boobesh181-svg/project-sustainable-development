from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

from sklearn.ensemble import IsolationForest  # type: ignore[import]


_MODEL_PATH = Path("./model/isolation_forest.pkl")


def _load_model() -> IsolationForest | None:
    if not _MODEL_PATH.exists():
        return None
    try:
        with _MODEL_PATH.open("rb") as f:
            model: IsolationForest = pickle.load(f)
        return model
    except Exception:  # pragma: no cover - defensive
        return None


def score_anomaly(payload: dict[str, Any]) -> dict[str, float]:
    """Score anomaly payload using IsolationForest if model exists.

    If the model file is not present or cannot be loaded, returns
    a deterministic 0.0 score.
    """

    model = _load_model()
    if model is None:
        return {"ml_score": 0.0}

    # Extremely small feature stub; real implementation would map payload -> vector
    features = [[float(hash(str(payload)) % 1000)]]
    score = float(model.decision_function(features)[0])
    return {"ml_score": score}
