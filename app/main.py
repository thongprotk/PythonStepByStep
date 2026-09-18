from contextlib import asynccontextmanager

import numpy as np
from fastapi import FastAPI

from app.api.routes import chat, cv, db, docs_tools, health, mida_assistant, predict
from app.core.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    model = predict.get_model()
    loaded = False
    try:
        loaded = model.load(settings.model_path)
    except Exception:  # noqa: BLE001 — any load failure falls back to seeding
        # Corrupt/partial file (e.g. pod killed mid-write) — fall through to seeding.
        loaded = False
    if not loaded:
        # Seed a tiny demo model (y = 2*x0 + 3*x1 + 1)
        # so POST /predict works immediately without manual /train.
        x = np.array([[1.0, 2.0], [2.0, 1.0], [3.0, 4.0], [4.0, 3.0]])
        y = 2 * x[:, 0] + 3 * x[:, 1] + 1
        model.train(x, y)
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

app.include_router(health.router)
app.include_router(predict.router)
app.include_router(chat.router)
app.include_router(mida_assistant.router)
app.include_router(docs_tools.router)
app.include_router(cv.router)
app.include_router(db.router)
