"""Inference for the academic early-warning model.

Loads the JSON artifact produced by scripts.train_risk_model and scores a
student in pure Python — no scikit-learn / numpy needed at run time. The score
is a calibrated logistic probability; the explainability layer decomposes it
into per-feature contributions (coefficient x standardized value, i.e. a linear
SHAP), so we can tell the student *why* they are flagged, not just that they are.

Design intent: the MODEL computes the risk and the factors; the LLM / UI only
narrates them. Mirrors the project thesis ("rules engine computes, LLM narrates")
for the predictive layer.
"""
import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from services.risk_features import FEATURE_COPY, FEATURE_NAMES, extract_features

ARTIFACT = Path(__file__).resolve().parent.parent / "ai" / "artifacts" / "risk_model.json"

# a contribution must clear this (in log-odds) to be worth showing to a human
_FACTOR_EPS = 0.05

# practical next step tied to each risk-raising factor
_ACTIONS = {
    "first_year_gpa": "Book a session with your academic advisor to build a focused recovery plan.",
    "gpa_trend": "Your GPA is trending down — consider a lighter, well-balanced load next term to stabilize it.",
    "failed_courses": "Prioritize retaking failed courses early — the latest grade replaces the F in your CGPA.",
    "low_grade_rate": "Use tutoring and office hours for the subjects where you scored in the D/F range.",
}


@lru_cache(maxsize=1)
def load_model() -> Optional[Dict]:
    if not ARTIFACT.exists():
        return None
    try:
        data = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    # the saved order must match the code's feature order
    if data.get("feature_names") != FEATURE_NAMES:
        return None
    return data


def _sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


def _band(p: float, bands: Dict) -> str:
    if p >= bands.get("high", 0.6):
        return "high"
    if p >= bands.get("moderate", 0.3):
        return "moderate"
    return "low"


def _format_detail(name: str, value: float) -> str:
    copy = FEATURE_COPY.get(name, {})
    detail = copy.get("detail", "")
    return detail.format(value=value, magnitude=abs(value), pct=value * 100)


def score_vector(model: Dict, features: Dict[str, float]) -> Dict:
    """Probability + per-feature log-odds contributions for one feature dict."""
    mean = model["scaler_mean"]
    scale = model["scaler_scale"]
    coef = model["coef"]
    z = model["intercept"]
    contributions: List[Dict] = []
    for i, name in enumerate(FEATURE_NAMES):
        x = float(features[name])
        std = (x - mean[i]) / scale[i] if scale[i] else 0.0
        c = coef[i] * std
        z += c
        contributions.append({"name": name, "value": round(x, 3), "contribution": round(c, 3)})
    return {"probability": _sigmoid(z), "contributions": contributions}


def model_info() -> Optional[Dict]:
    """Metadata for the admin 'about this model' panel."""
    model = load_model()
    if not model:
        return None
    return {
        "model": model.get("model"),
        "trained_at": model.get("trained_at"),
        "feature_names": model.get("feature_names"),
        "train_min_main_semesters": model.get("train_min_main_semesters"),
        "metrics": model.get("metrics", {}),
    }


def _explain(contributions: List[Dict]) -> Dict:
    """Split contributions into risk-raising factors and protective factors,
    each with human copy, sorted by magnitude."""
    raising, protective, actions = [], [], []
    for c in sorted(contributions, key=lambda d: -d["contribution"]):
        copy = FEATURE_COPY.get(c["name"], {})
        if c["contribution"] > _FACTOR_EPS:
            raising.append({
                "name": c["name"],
                "label": copy.get("label", c["name"]),
                "detail": _format_detail(c["name"], c["value"]),
                "value": c["value"],
                "weight": c["contribution"],
            })
            if c["name"] in _ACTIONS:
                actions.append(_ACTIONS[c["name"]])
    for c in sorted(contributions, key=lambda d: d["contribution"]):
        if c["contribution"] < -_FACTOR_EPS:
            copy = FEATURE_COPY.get(c["name"], {})
            protective.append({
                "name": c["name"],
                "label": copy.get("protective", copy.get("label", c["name"])),
                "value": c["value"],
                "weight": c["contribution"],
            })
    return {"factors": raising, "protective": protective, "actions": actions}


async def predict_risk(student_id: int, db: AsyncSession) -> Optional[Dict]:
    """Full early-warning assessment for one student, or None if the model is
    unavailable or the student has no graded record yet."""
    model = load_model()
    if not model:
        return None
    feat = await extract_features(student_id, db)
    if feat is None:
        return None

    scored = score_vector(model, feat["features"])
    p = scored["probability"]
    band = _band(p, model.get("bands", {}))
    explained = _explain(scored["contributions"])

    maturity = feat["maturity"]
    horizon = "forecast" if maturity < model.get("train_min_main_semesters", 3) else "assessment"

    return {
        "risk_score": round(p, 3),
        "risk_band": band,
        "horizon": horizon,            # "forecast" (outcome still open) vs "assessment"
        "maturity": maturity,          # main semesters completed
        "features": feat["features"],
        "factors": explained["factors"],
        "protective": explained["protective"],
        "recommended_actions": explained["actions"],
        "model": {
            "trained_at": model.get("trained_at"),
            "auc": model.get("metrics", {}).get("cv_auc_mean"),
            "n_train": model.get("metrics", {}).get("n_train"),
        },
    }
