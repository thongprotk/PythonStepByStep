from fastapi import APIRouter

from app.llm.client import LLMClient
from app.schemas.common import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["llm"])


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    client = LLMClient()
    reply = client.ask(request.message)
    return ChatResponse(reply=reply)
