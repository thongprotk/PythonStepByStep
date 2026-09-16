import numpy as np


def _cv2():
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError(
            "OpenCV (cv2) is not installed; install opencv-python to use /cv"
        ) from exc
    return cv2


def to_grayscale(image_bytes: bytes) -> np.ndarray:
    if not image_bytes:
        raise ValueError("Empty image data")
    cv2 = _cv2()
    array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Could not decode image bytes (unsupported or corrupt file)")
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def encode_png(gray: np.ndarray) -> bytes:
    cv2 = _cv2()
    ok, buf = cv2.imencode(".png", gray)
    if not ok:
        raise RuntimeError("Failed to encode grayscale image to PNG")
    return bytes(buf)
