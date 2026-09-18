from fastapi import APIRouter, HTTPException

from app.db.qa_log import log_qa_session
from app.llm.mida_prompt import SYSTEM_PROMPT, build_user_content, parse_assistant_reply
from app.llm.provider import get_llm_client
from app.schemas.common import MidaAssistantRequest, MidaAssistantResponse
from app.tools.doc_retriever import retrieve_relevant_chunks

router = APIRouter(prefix="/mida-assistant", tags=["llm"])


@router.post("", response_model=MidaAssistantResponse)
def ask_mida_assistant(request: MidaAssistantRequest) -> MidaAssistantResponse:
    # A chat agent that hasn't run its own RAG step gets grounding for free:
    # fall back to keyword retrieval over docs/ (populated by /docs/scrape).
    retrieved_chunks = request.retrieved_chunks or retrieve_relevant_chunks(
        request.user_message
    )
    try:
        user_content = build_user_content(
            user_message=request.user_message,
            retrieved_chunks=retrieved_chunks,
            customer_config=request.customer_config,
            feature_catalog=request.feature_catalog,
            recent_history=request.recent_history,
            max_history_turns=request.max_history_turns,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        client = get_llm_client()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    try:
        raw_reply = client.ask_with_system(
            SYSTEM_PROMPT, user_content, model=request.model
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"LLM provider error: {exc}"
        ) from exc

    try:
        parsed = parse_assistant_reply(raw_reply)
    except ValueError as exc:
        raise HTTPException(
            status_code=502, detail=f"model reply did not match contract: {exc}"
        ) from exc

    log_qa_session(
        "/mida-assistant",
        request.user_message,
        parsed["answer"],
        extra={
            "confidence": parsed["confidence"],
            "in_scope": parsed["in_scope"],
            "needs_escalation": parsed["needs_escalation"],
        },
    )
    return MidaAssistantResponse(**parsed)
