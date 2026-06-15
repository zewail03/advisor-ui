"""Train the academic early-warning model and save it as a small JSON artifact.

The story (committee-facing):
  * LABEL  — did a student ever fall to a warning / probation / dismissal? This
    only becomes possible from the 3rd MAIN semester on (Dr. Ashraf §1–§2), so
    it is a genuinely *later* outcome.
  * FEATURES — only the first two MAIN semesters (see services.risk_features),
    so the model predicts forward and never just restates the current CGPA.
  * TRAINING SET — senior cohorts that have completed >= 3 main semesters, whose
    outcome is therefore already known and uncensored.
  * PREDICTION TARGETS (at run time) — current first / second-year students,
    whose outcome is not yet decided. That is exactly who we want to flag early.

We fit a StandardScaler + LogisticRegression with scikit-learn here, then write
the scaler stats + coefficients + metrics to JSON. Inference (services.risk_model)
reads that JSON and computes the sigmoid in pure Python, so the running backend
needs no scikit-learn / numpy at all.

Run (Postgres must be up):
  .\\venv\\Scripts\\python.exe -m scripts.train_risk_model
"""
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

PG_URL = os.environ.get("PG_URL", "postgresql+asyncpg://aiu:aiu_dev@localhost:5433/aiu")
os.environ.setdefault("DATABASE_URL", PG_URL)

import numpy as np  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    accuracy_score,
    confusion_matrix,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import cross_val_score, train_test_split  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402
from sqlalchemy import text  # noqa: E402

from core.database import AsyncSessionLocal  # noqa: E402
from services.risk_features import FEATURE_NAMES, extract_features  # noqa: E402

ARTIFACT = Path(__file__).resolve().parent.parent / "ai" / "artifacts" / "risk_model.json"
TRAIN_MIN_MAIN_SEMESTERS = 3   # need the outcome window to have opened
BANDS = {"moderate": 0.30, "high": 0.60}


async def collect():
    """Return (X, y, meta) over every student that has a feature vector."""
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(text(
            """
            SELECT s.student_id, s.student_code, s.math0_passed,
                   COALESCE(MAX(a.warning_count), 0) AS max_warn,
                   BOOL_OR(a.status IN ('Probation', 'Dismissed')) AS ever_bad
            FROM students s
            LEFT JOIN academic_standing a ON a.student_code = s.student_code
            GROUP BY s.student_id, s.student_code, s.math0_passed
            ORDER BY s.student_id
            """
        ))).all()

        X, y, maturity = [], [], []
        for student_id, _code, math0, max_warn, ever_bad in rows:
            feat = await extract_features(student_id, db, math0_passed=math0)
            if feat is None:
                continue
            label = 1 if (int(max_warn or 0) >= 1 or bool(ever_bad)) else 0
            X.append(feat["vector"])
            y.append(label)
            maturity.append(feat["maturity"])
    return np.array(X, dtype=float), np.array(y, dtype=int), np.array(maturity, dtype=int)


def main():
    X, y, maturity = asyncio.run(collect())
    mature = maturity >= TRAIN_MIN_MAIN_SEMESTERS
    Xt, yt = X[mature], y[mature]

    n_pos = int(yt.sum())
    print(f"feature rows: {len(X)} | trainable (>= {TRAIN_MIN_MAIN_SEMESTERS} main sems): "
          f"{len(Xt)} | at-risk outcomes: {n_pos} ({n_pos / max(len(Xt), 1):.1%})")
    if len(Xt) < 30 or n_pos < 5 or n_pos == len(Xt):
        raise SystemExit("Not enough labelled signal to train a model.")

    scaler = StandardScaler().fit(Xt)
    Xs = scaler.transform(Xt)

    # honest held-out metrics
    X_tr, X_te, y_tr, y_te = train_test_split(
        Xs, yt, test_size=0.25, random_state=42, stratify=yt
    )
    clf = LogisticRegression(max_iter=2000, C=1.0)
    clf.fit(X_tr, y_tr)
    proba = clf.predict_proba(X_te)[:, 1]
    pred = (proba >= 0.5).astype(int)
    auc = float(roc_auc_score(y_te, proba)) if len(set(y_te)) > 1 else float("nan")
    cv_auc = cross_val_score(
        LogisticRegression(max_iter=2000), Xs, yt, cv=5, scoring="roc_auc"
    )
    cm = confusion_matrix(y_te, pred).tolist()

    print(f"held-out  AUC={auc:.3f}  acc={accuracy_score(y_te, pred):.3f}  "
          f"precision={precision_score(y_te, pred, zero_division=0):.3f}  "
          f"recall={recall_score(y_te, pred, zero_division=0):.3f}")
    print(f"5-fold CV AUC={cv_auc.mean():.3f} ± {cv_auc.std():.3f}")
    print(f"confusion matrix [tn fp / fn tp]: {cm}")

    # production model: refit on ALL mature data
    final = LogisticRegression(max_iter=2000, C=1.0).fit(Xs, yt)
    coef = final.coef_[0].tolist()
    print("\nstandardized coefficients (global importance):")
    for name, c in sorted(zip(FEATURE_NAMES, coef), key=lambda kv: -abs(kv[1])):
        print(f"  {name:<20} {c:+.3f}")

    artifact = {
        "model": "logistic_regression",
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "feature_names": FEATURE_NAMES,
        "scaler_mean": scaler.mean_.tolist(),
        "scaler_scale": scaler.scale_.tolist(),
        "coef": coef,
        "intercept": float(final.intercept_[0]),
        "bands": BANDS,
        "train_min_main_semesters": TRAIN_MIN_MAIN_SEMESTERS,
        "metrics": {
            "n_train": int(len(Xt)),
            "n_at_risk": n_pos,
            "base_rate": round(n_pos / len(Xt), 3),
            "holdout_auc": round(auc, 3),
            "holdout_accuracy": round(float(accuracy_score(y_te, pred)), 3),
            "holdout_precision": round(float(precision_score(y_te, pred, zero_division=0)), 3),
            "holdout_recall": round(float(recall_score(y_te, pred, zero_division=0)), 3),
            "cv_auc_mean": round(float(cv_auc.mean()), 3),
            "cv_auc_std": round(float(cv_auc.std()), 3),
            "confusion_matrix": cm,
        },
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    print(f"\nsaved -> {ARTIFACT}")


if __name__ == "__main__":
    main()
