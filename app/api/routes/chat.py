from fastapi import APIRouter, HTTPException

from app.db.qa_log import log_qa_session
from app.llm.provider import get_llm_client
from app.schemas.common import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["llm"])


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    try:
        client = get_llm_client()
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
    log_qa_session("/chat", request.message, reply)
    return ChatResponse(reply=reply)
