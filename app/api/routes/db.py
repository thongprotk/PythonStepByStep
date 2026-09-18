from fastapi import APIRouter, HTTPException

from app.db.supabase_client import get_supabase
from app.schemas.common import Todo, TodoCreate

router = APIRouter(prefix="/db", tags=["db"])

TABLE = "todos"


@router.get("/health")
def db_health() -> dict:
    """Ping Supabase (reads 1 row). Separate from /health so k8s probes stay fast."""
    try:
        client = get_supabase()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    try:
        client.table(TABLE).select("id").limit(1).execute()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Supabase error: {exc}") from exc
    return {"status": "ok"}


@router.get("/todos", response_model=list[Todo])
def list_todos() -> list[Todo]:
    try:
        client = get_supabase()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    try:
        response = client.table(TABLE).select("*").execute()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Supabase error: {exc}") from exc
    return [Todo(**row) for row in response.data]


@router.post("/todos", response_model=Todo, status_code=201)
def create_todo(payload: TodoCreate) -> Todo:
    try:
        client = get_supabase()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    try:
        response = client.table(TABLE).insert({"name": payload.name}).execute()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Supabase error: {exc}") from exc
    if not response.data:
        raise HTTPException(status_code=502, detail="Supabase returned no data")
    return Todo(**response.data[0])
