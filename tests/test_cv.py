import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _red_square_png() -> bytes:
    img = np.zeros((10, 10, 3), dtype=np.uint8)
    img[:, :] = (0, 0, 255)
    ok, buf = cv2.imencode(".png", img)
    assert ok
    return bytes(buf)


def test_grayscale_ok():
    response = client.post(
        "/cv/grayscale",
        files={"image": ("red.png", _red_square_png(), "image/png")},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert len(response.content) > 0


def test_grayscale_corrupt_returns_422():
    response = client.post(
        "/cv/grayscale",
        files={"image": ("bad.bin", b"not-an-image", "application/octet-stream")},
    )
    assert response.status_code == 422


def test_grayscale_empty_returns_422():
    response = client.post(
        "/cv/grayscale",
        files={"image": ("empty.png", b"", "image/png")},
    )
    assert response.status_code == 422
