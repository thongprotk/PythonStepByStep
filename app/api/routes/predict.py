import numpy as np
from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.ml.model import RegressionModel
from app.schemas.common import (
    PredictRequest,
    PredictResponse,
    TrainRequest,
    TrainResponse,
)

router = APIRouter(prefix="/predict", tags=["ml"])

_model = RegressionModel()


def get_model() -> RegressionModel:
    return _model


@router.post("/train", response_model=TrainResponse)
def train(request: TrainRequest) -> TrainResponse:
    if not request.x or not request.y:
        raise HTTPException(status_code=422, detail="x and y must be non-empty")
    try:
        x = np.array(request.x, dtype=float)
        y = np.array(request.y, dtype=float)
        _model.train(x, y)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    # Best-effort persistence so a pod restart keeps the trained model.
    try:
        _model.save(get_settings().model_path)
    except Exception:  # noqa: BLE001, S110
        pass  # persistence is optional, train already succeeded
    return TrainResponse(n_samples=len(request.y), n_features=len(request.x[0]))


@router.post("", response_model=PredictResponse)
def predict(request: PredictRequest) -> PredictResponse:
    try:
        result = _model.predict(request.features)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return PredictResponse(prediction=result)
