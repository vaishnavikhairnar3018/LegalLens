"""
LenseScan Image Preprocessing.
Deskew, denoise, and enhance label images before OCR.
"""

import cv2
import numpy as np
from typing import Tuple


def normalize_upload(image_bytes: bytes, max_dimension: int = 2048) -> bytes:
    """
    Shrink an uploaded photo once, on the server, to at most max_dimension pixels (INTER_AREA,
    which keeps small print sharp), and return it as lossless PNG bytes.

    Calibration and OCR must both work on these bytes. If the marker were measured on the full
    photo while OCR read a shrunken copy, px/mm and the letter boxes would be on different pixel
    grids and every letter height in mm would be wrong. Hash the raw upload, never this output.
    """
    image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Failed to decode image. File may be corrupted.")
    image = _resize_if_needed(image, max_dimension=max_dimension)
    ok, buf = cv2.imencode(".png", image, [cv2.IMWRITE_PNG_COMPRESSION, 1])
    if not ok:
        raise ValueError("Failed to re-encode image after resizing.")
    return buf.tobytes()


def preprocess_image(image_bytes: bytes) -> np.ndarray:
    """
    Full preprocessing pipeline for label images.

    Steps:
    1. Decode image from bytes
    2. Resize if too large (preserve aspect ratio)
    3. Convert to grayscale
    4. Denoise with Gaussian blur
    5. Apply adaptive thresholding for better text contrast
    6. Deskew based on text line angle detection

    Args:
        image_bytes: Raw image file bytes (JPEG or PNG).

    Returns:
        Preprocessed image as numpy array suitable for OCR.
    """
    # Decode image from bytes
    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if image is None:
        raise ValueError("Failed to decode image. File may be corrupted.")

    # Resize if too large (max dimension 2048px for OCR performance)
    image = _resize_if_needed(image, max_dimension=2048)

    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Denoise — light Gaussian blur to reduce noise while preserving edges
    denoised = cv2.GaussianBlur(gray, (3, 3), 0)

    # Enhance contrast via CLAHE (Contrast Limited Adaptive Histogram Equalization)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(denoised)

    # Deskew the image
    deskewed = _deskew(enhanced)

    return deskewed


def preprocess_for_ocr(image_bytes: bytes) -> Tuple[np.ndarray, np.ndarray]:
    """
    Returns both the preprocessed image (for OCR) and the original color image
    (for bounding box visualization).

    Args:
        image_bytes: Raw image file bytes.

    Returns:
        Tuple of (preprocessed_gray, original_color) numpy arrays.
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    original = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if original is None:
        raise ValueError("Failed to decode image. File may be corrupted.")

    original = _resize_if_needed(original, max_dimension=2048)
    preprocessed = preprocess_image(image_bytes)

    return preprocessed, original


def _resize_if_needed(image: np.ndarray, max_dimension: int = 2048) -> np.ndarray:
    """Resize image if any dimension exceeds max_dimension, preserving aspect ratio."""
    height, width = image.shape[:2]
    if max(height, width) <= max_dimension:
        return image

    scale = max_dimension / max(height, width)
    new_width = int(width * scale)
    new_height = int(height * scale)
    return cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)


def _deskew(image: np.ndarray) -> np.ndarray:
    """
    Deskew image using Hough Line Transform to detect text rotation angle.

    Only applies correction for small angles (< 15°) to avoid
    over-rotating images that are already straight.
    """
    # Edge detection for line finding
    edges = cv2.Canny(image, 50, 150, apertureSize=3)

    # Detect lines using probabilistic Hough Transform
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180, threshold=100,
        minLineLength=100, maxLineGap=10,
    )

    if lines is None:
        return image

    # Calculate dominant angle from detected lines
    angles = []
    for line in lines:
        pts = line.reshape(-1)
        if len(pts) >= 4:
            x1, y1, x2, y2 = pts[:4]
            angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
            # Only consider near-horizontal lines (within 15° of horizontal)
            if abs(angle) < 15:
                angles.append(angle)

    if not angles:
        return image

    # Use median angle for robustness against outliers
    median_angle = np.median(angles)

    # Only deskew if the angle is significant enough (> 0.5°)
    if abs(median_angle) < 0.5:
        return image

    # Rotate image to correct the skew
    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    rotation_matrix = cv2.getRotationMatrix2D(center, median_angle, 1.0)
    rotated = cv2.warpAffine(
        image, rotation_matrix, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )

    return rotated


def get_dpi_from_image(image_bytes: bytes, default_dpi: int = 300) -> int:
    """
    Attempt to extract DPI from image EXIF data.
    Falls back to default_dpi if EXIF data is unavailable.

    Args:
        image_bytes: Raw image bytes.
        default_dpi: Fallback DPI value.

    Returns:
        DPI as integer.
    """
    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(image_bytes))
        dpi_info = img.info.get("dpi")
        if dpi_info and isinstance(dpi_info, tuple) and dpi_info[0] > 0:
            return int(dpi_info[0])
    except Exception:
        pass

    return default_dpi
