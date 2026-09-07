from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    app_name: str


class PredictRequest(BaseModel):
    features: list[float]


class PredictResponse(BaseModel):
    prediction: float


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
