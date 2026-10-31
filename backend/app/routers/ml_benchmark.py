"""
LegalLens AI — Machine Learning Benchmark & Categorization Router.
Exposes Supervised Learning models, metrics, and live product classification.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import joblib

router = APIRouter(prefix="/ml", tags=["Machine Learning Benchmark"])

DOCS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "docs"
MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
MODEL_PATH = MODELS_DIR / "product_classifier.joblib"
METRICS_PATH = DOCS_DIR / "model_metrics.json"
DASHBOARD_PATH = DOCS_DIR / "ml_model_accuracy_dashboard.html"

# Global model cache
_cached_pipeline = None


def get_pipeline():
    global _cached_pipeline
    if _cached_pipeline is None and MODEL_PATH.exists():
        try:
            _cached_pipeline = joblib.load(MODEL_PATH)
        except Exception:
            _cached_pipeline = None
    return _cached_pipeline


class CategorizeRequest(BaseModel):
    product_name: str


class CategorizeResponse(BaseModel):
    input_text: str
    predicted_category: str
    is_liquid_or_viscous: bool
    statutory_schedule_ii_rule: str
    model_used: str


@router.get("/metrics", summary="Get Supervised Learning Benchmark Metrics")
async def get_ml_metrics() -> Dict[str, Any]:
    """Return accuracy, F1-scores, and cross-validation results for all 6 trained Supervised Learning models."""
    if not METRICS_PATH.exists():
        raise HTTPException(status_code=404, detail="Model metrics not found. Please run training script first.")
    with open(METRICS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


@router.get("/top-terms", summary="Words the Linear SVM weighs most for each category")
async def get_top_terms(n: int = Query(8, ge=1, le=50)) -> Dict[str, Any]:
    """
    For each category, the n vocabulary words with the largest positive Linear SVM weight,
    read from the saved TF-IDF + LinearSVC pipeline. Public, like /metrics: model information,
    not inspection data.
    """
    pipe = get_pipeline()
    if pipe is None:
        raise HTTPException(status_code=503, detail="Classification model not ready.")
    vocab = pipe.named_steps["tfidf"].get_feature_names_out()
    clf = pipe.named_steps["clf"]

    categories = []
    for row, category in enumerate(clf.classes_):
        weights = clf.coef_[row]
        top = [i for i in weights.argsort()[::-1][:n] if weights[i] > 0]
        categories.append({
            "category": str(category),
            "terms": [{"term": str(vocab[i]), "weight": round(float(weights[i]), 4)} for i in top],
        })
    return {"model": "Linear SVM", "categories": categories}


@router.post("/categorize", response_model=CategorizeResponse, summary="Categorize Product via Supervised Learning")
async def categorize_product(req: CategorizeRequest):
    """
    Predict FMCG commodity category using the best Supervised Learning pipeline (Linear SVM).
    Maps predicted category to statutory LMPC Rule 7(2) font-height guidelines.
    """
    pipe = get_pipeline()
    if pipe is None:
        raise HTTPException(status_code=503, detail="Classification model not ready.")

    query = req.product_name.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Product name cannot be empty.")

    pred_cat = str(pipe.predict([query])[0])

    # Statutory LMPC Rule 7(2) mapping: liquid vs solid rules
    is_liquid = pred_cat in ["Beverages & Dairy", "Condiments & Sauces"] or any(
        w in query.lower() for w in ["oil", "liquid", "shampoo", "syrup", "juice", "milk", "sauce"]
    )
    schedule_rule = (
        "Rule 7(2): Liquid Commodity (Volume in mL / L) — Minimum font height scaled to pack volume"
        if is_liquid
        else "Rule 7(2): Solid / Granular Commodity (Weight in g / kg) — Minimum font height scaled to pack weight"
    )

    return CategorizeResponse(
        input_text=query,
        predicted_category=pred_cat,
        is_liquid_or_viscous=is_liquid,
        statutory_schedule_ii_rule=schedule_rule,
        model_used="Linear Support Vector Machine (Linear SVM) + TF-IDF",
    )


@router.get("/dashboard", response_class=HTMLResponse, summary="View Interactive ML Accuracy Dashboard")
async def view_ml_dashboard():
    """Serves the interactive Chart.js evaluation dashboard for website and presentation embedding."""
    if not DASHBOARD_PATH.exists():
        raise HTTPException(status_code=404, detail="Dashboard HTML not generated.")
    with open(DASHBOARD_PATH, "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)

