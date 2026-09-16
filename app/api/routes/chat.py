from fastapi import APIRouter, HTTPException

from app.llm.client import LLMClient
from app.schemas.common import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["llm"])


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    try:
        client = LLMClient()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    try:
        reply = client.ask(request.message, model=request.model)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"LLM provider error: {exc}"
        ) from exc
    return ChatResponse(reply=reply)
