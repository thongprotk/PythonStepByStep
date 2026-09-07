from fastapi import APIRouter, HTTPException

from app.ml.model import RegressionModel
from app.schemas.common import PredictRequest, PredictResponse

router = APIRouter(prefix="/predict", tags=["ml"])

_model = RegressionModel()


@router.post("", response_model=PredictResponse)
def predict(request: PredictRequest) -> PredictResponse:
    try:
        result = _model.predict(request.features)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PredictResponse(prediction=result)
