from typing import Any

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


class MidaAssistantRequest(BaseModel):
    user_message: str
    retrieved_chunks: list[str] = []
    customer_config: dict[str, Any] = {}
    feature_catalog: Any = []
    recent_history: list[dict[str, Any]] = []
    max_history_turns: int = 5
    model: str | None = None


class MidaAssistantResponse(BaseModel):
    answer: str
    cited_sources: list[str]
    suggested_features: list[str]
    confidence: float
    needs_escalation: bool
    in_scope: bool


class Todo(BaseModel):
    id: int | None = None
    name: str


class TodoCreate(BaseModel):
    name: str
