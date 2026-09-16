from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    app_name: str
    db: str = "ok"


class TrainRequest(BaseModel):
    x: list[list[float]]
    y: list[float]


class TrainResponse(BaseModel):
    n_samples: int
    n_features: int


class PredictRequest(BaseModel):
    features: list[float]


class PredictResponse(BaseModel):
    prediction: float


class ChatRequest(BaseModel):
    message: str
    model: str | None = None


class ChatResponse(BaseModel):
    reply: str
