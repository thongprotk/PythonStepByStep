from sklearn.linear_model import LinearRegression
import numpy as np


class RegressionModel:
    """Thin wrapper around a scikit-learn estimator so routes don't touch sklearn directly."""

    def __init__(self) -> None:
        self._estimator = LinearRegression()
        self._fitted = False

    def train(self, x: np.ndarray, y: np.ndarray) -> None:
        self._estimator.fit(x, y)
        self._fitted = True

    def predict(self, features: list[float]) -> float:
        if not self._fitted:
            raise RuntimeError("Model has not been trained yet")
        x = np.array(features).reshape(1, -1)
        return float(self._estimator.predict(x)[0])
