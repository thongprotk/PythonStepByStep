from fastapi.testclient import TestClient

from app.api.routes import predict
from app.core.config import get_settings
from app.main import app
from app.ml.model import RegressionModel

client = TestClient(app)


def _fresh_model(monkeypatch, tmp_path):
    fresh = RegressionModel()
    monkeypatch.setattr(predict, "_model", fresh)
    # Isolate persistence: train endpoint saves to tmp instead of ./model.joblib.
    settings = predict.get_settings()
    monkeypatch.setattr(settings, "model_path", str(tmp_path / "model.joblib"))
    return fresh


def test_predict_untrained_returns_400(monkeypatch, tmp_path):
    _fresh_model(monkeypatch, tmp_path)
    response = client.post("/predict", json={"features": [1.0, 2.0]})
    assert response.status_code == 400


def test_train_then_predict(monkeypatch, tmp_path):
    _fresh_model(monkeypatch, tmp_path)
    train = client.post(
        "/predict/train",
        json={"x": [[1.0], [2.0], [3.0]], "y": [2.0, 4.0, 6.0]},
    )
    assert train.status_code == 200
    assert train.json()["n_samples"] == 3

    response = client.post("/predict", json={"features": [4.0]})
    assert response.status_code == 200
    assert abs(response.json()["prediction"] - 8.0) < 1e-6


def test_train_mismatched_shapes_returns_422(monkeypatch, tmp_path):
    _fresh_model(monkeypatch, tmp_path)
    response = client.post(
        "/predict/train",
        json={"x": [[1.0], [2.0]], "y": [1.0]},
    )
    assert response.status_code == 422


def test_predict_wrong_dimension_returns_422(monkeypatch, tmp_path):
    _fresh_model(monkeypatch, tmp_path)
    client.post(
        "/predict/train",
        json={"x": [[1.0], [2.0], [3.0]], "y": [2.0, 4.0, 6.0]},
    )
    response = client.post("/predict", json={"features": [1.0, 2.0]})
    assert response.status_code == 422


def test_lifespan_seeds_demo_model(monkeypatch, tmp_path):
    """Startup without a persisted file seeds y = 2x0 + 3x1 + 1."""
    get_settings.cache_clear()
    monkeypatch.setenv("MODEL_PATH", str(tmp_path / "missing.joblib"))
    try:
        with TestClient(app) as lifespan_client:
            response = lifespan_client.post("/predict", json={"features": [1.0, 2.0]})
            assert response.status_code == 200
            assert abs(response.json()["prediction"] - 9.0) < 1e-6
    finally:
        get_settings.cache_clear()


def test_lifespan_survives_corrupt_model_file(monkeypatch, tmp_path):
    """A corrupt model.joblib (e.g. pod killed mid-write) falls back to seeding."""
    corrupt = tmp_path / "model.joblib"
    corrupt.write_bytes(b"not a valid joblib payload")
    get_settings.cache_clear()
    monkeypatch.setenv("MODEL_PATH", str(corrupt))
    try:
        with TestClient(app) as lifespan_client:
            response = lifespan_client.post("/predict", json={"features": [1.0, 2.0]})
            assert response.status_code == 200
    finally:
        get_settings.cache_clear()
