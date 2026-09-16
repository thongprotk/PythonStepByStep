from pathlib import Path

import numpy as np
from sklearn.linear_model import LinearRegression


class RegressionModel:
    """Thin wrapper around a scikit-learn estimator so routes don't touch sklearn directly."""

    def __init__(self) -> None:
        self._estimator = LinearRegression()
        self._fitted = False
        self._n_features: int | None = None

    @property
    def is_fitted(self) -> bool:
        return self._fitted

    @property
    def n_features(self) -> int | None:
        return self._n_features

    def train(self, x: np.ndarray, y: np.ndarray) -> None:
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        if x.ndim != 2 or x.shape[0] == 0 or x.shape[1] == 0:
            raise ValueError("X must be a non-empty 2D array")
        if y.ndim != 1 or y.shape[0] != x.shape[0]:
            raise ValueError("y must be a 1D array with the same row count as X")
        self._estimator.fit(x, y)
        self._fitted = True
        self._n_features = x.shape[1]

    def predict(self, features: list[float]) -> float:
        if not self._fitted:
            raise RuntimeError("Model has not been trained yet")
        if not features:
            raise ValueError("features must be a non-empty list")
        if self._n_features is not None and len(features) != self._n_features:
            raise ValueError(
                f"Expected {self._n_features} features, got {len(features)}"
            )
        x = np.array(features, dtype=float).reshape(1, -1)
        return float(self._estimator.predict(x)[0])

    def save(self, path: str | Path) -> None:
        if not self._fitted:
            raise RuntimeError("Cannot save an unfitted model")
        import joblib

        joblib.dump(
            {"estimator": self._estimator, "n_features": self._n_features},
            path,
        )

    def load(self, path: str | Path) -> bool:
        """Load a persisted model. Returns True on success, False if file missing."""
        import joblib

        p = Path(path)
        if not p.exists():
            return False
        payload = joblib.load(p)
        self._estimator = payload["estimator"]
        self._n_features = payload.get("n_features")
        self._fitted = True
        return True
