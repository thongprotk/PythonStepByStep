"""Supabase client factory (PostgREST). Lazy import so the app boots without the dep."""

from app.core.config import get_settings


def get_supabase():
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_key:
        raise RuntimeError(
            "SUPABASE_URL / SUPABASE_KEY is not configured; "
            "set them in .env or environment before calling /db"
        )
    try:
        from supabase import create_client
    except ImportError as exc:
        raise RuntimeError(
            "supabase package is not installed; run: pip install supabase"
        ) from exc
    return create_client(settings.supabase_url, settings.supabase_key)
