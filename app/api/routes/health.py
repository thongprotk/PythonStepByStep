from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.common import HealthResponse

router = APIRouter(prefix="/health", tags=["health"])


def check_db(database_url: str) -> str:
    try:
        from sqlalchemy import create_engine, text
    except ImportError:
        return "skipped: sqlalchemy not installed"
    try:
        engine = create_engine(database_url, connect_args={"timeout": 5})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return "ok"
    except Exception as exc:  # noqa: BLE001 — any DB failure is reported as a string
        return f"error: {exc}"


@router.get("", response_model=HealthResponse)
def health_check() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        db=check_db(settings.database_url),
    )
