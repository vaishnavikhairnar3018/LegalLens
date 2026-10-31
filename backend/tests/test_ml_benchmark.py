"""
Unit and integration tests for Supervised Learning ML benchmark and categorization router.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_ml_metrics_endpoint():
    """Verify that ML benchmark endpoint returns accuracy for all 6 models."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/v1/ml/metrics")
        assert res.status_code == 200
        data = res.json()
        assert "models_benchmark" in data
        assert len(data["models_benchmark"]) == 6
        model_names = [m["model_name"] for m in data["models_benchmark"]]
        assert "Random Forest" in model_names
        assert "Linear SVM" in model_names
        assert "Logistic Regression" in model_names
        assert "Multinomial Naive Bayes" in model_names


@pytest.mark.asyncio
async def test_ml_categorize_endpoint():
    """Verify live categorization of Indian retail packaging strings."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Biscuits
        res1 = await client.post(
            "/api/v1/ml/categorize",
            json={"product_name": "Parle-G Glucose Biscuits 80g"},
        )
        assert res1.status_code == 200
        assert res1.json()["predicted_category"] == "Biscuits & Bakery"
        assert res1.json()["is_liquid_or_viscous"] is False

        # 2. Handwash (Personal Care)
        res2 = await client.post(
            "/api/v1/ml/categorize",
            json={"product_name": "Dettol Antiseptic Liquid Handwash 200ml"},
        )
        assert res2.status_code == 200
        assert res2.json()["predicted_category"] == "Personal Care & Cosmetics"
        assert res2.json()["is_liquid_or_viscous"] is True

        # 3. Detergent (Household & Cleaning)
        res3 = await client.post(
            "/api/v1/ml/categorize",
            json={"product_name": "Surf Excel Easy Wash Detergent Powder 1kg"},
        )
        assert res3.status_code == 200
        assert res3.json()["predicted_category"] == "Household & Cleaning"


@pytest.mark.asyncio
async def test_ml_top_terms_come_from_the_trained_classifier():
    """GET /ml/top-terms: for every category, the words with the largest Linear SVM weights,
    highest first, read from the saved model (not made up). Public, like /ml/metrics: it is
    model information, not inspection data."""
    import joblib
    from app.routers.ml_benchmark import MODEL_PATH

    pipe = joblib.load(MODEL_PATH)
    vocab = pipe.named_steps["tfidf"].get_feature_names_out()
    clf = pipe.named_steps["clf"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/v1/ml/top-terms", params={"n": 5})
    assert res.status_code == 200
    data = res.json()
    assert data["model"] == "Linear SVM"
    assert [c["category"] for c in data["categories"]] == [str(c) for c in clf.classes_]

    for row, category in enumerate(data["categories"]):
        terms = category["terms"]
        assert len(terms) == 5
        weights = [t["weight"] for t in terms]
        assert weights == sorted(weights, reverse=True)
        assert all(w > 0 for w in weights)
        # The top word and its weight match the model's own largest coefficient for this category
        best = clf.coef_[row].argmax()
        assert terms[0]["term"] == vocab[best]
        assert terms[0]["weight"] == pytest.approx(float(clf.coef_[row][best]), abs=1e-4)


@pytest.mark.asyncio
async def test_ml_top_terms_rejects_out_of_range_n():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/api/v1/ml/top-terms", params={"n": 0})).status_code == 422
        assert (await client.get("/api/v1/ml/top-terms", params={"n": 51})).status_code == 422


@pytest.mark.asyncio
async def test_ml_dashboard_html_endpoint():
    """Verify that interactive HTML dashboard is rendered."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/v1/ml/dashboard")
        assert res.status_code == 200
        assert "text/html" in res.headers["content-type"]
        assert "chart.js" in res.text.lower()
        assert "supervised learning" in res.text.lower()
