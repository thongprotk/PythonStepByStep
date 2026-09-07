from fastapi import FastAPI

from app.api.routes import chat, health, predict
from app.core.config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name, debug=settings.debug)

app.include_router(health.router)
app.include_router(predict.router)
app.include_router(chat.router)
