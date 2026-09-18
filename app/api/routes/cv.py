from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response

from app.cv.processor import encode_png, to_grayscale

router = APIRouter(prefix="/cv", tags=["cv"])

MAX_IMAGE_BYTES = 5 * 1024 * 1024


@router.post("/grayscale")
def grayscale(
    image: UploadFile = File(...),  # noqa: B008 — standard FastAPI idiom
) -> Response:
    if not image.filename:
        raise HTTPException(status_code=422, detail="No file uploaded")
    data = image.file.read()
    if not data:
        raise HTTPException(status_code=422, detail="Uploaded file is empty")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image too large (max 5MB)")
    try:
        gray = to_grayscale(data)
        png = encode_png(gray)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"CV processing failed: {exc}"
        ) from exc
    return Response(content=png, media_type="image/png")
