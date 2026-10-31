"""
LenseScan OCR Pipeline.
EasyOCR-based text extraction with bounding boxes and font height estimation.
All processing happens on our secure backend — no external API calls.
"""

import logging
from typing import List, Optional
import numpy as np
try:
    import easyocr
except ImportError:
    easyocr = None

from app.schemas.scan import OCRResult, BoundingBox
from app.utils.sanitizer import sanitize_ocr_text

logger = logging.getLogger(__name__)

# Singleton reader — EasyOCR model is heavy, load once
_reader = None


def get_reader(languages: List[str] = None):
    """
    Get or initialize the EasyOCR reader singleton.
    The model is loaded into memory once and reused for all requests.

    Args:
        languages: List of language codes (e.g., ['en', 'hi']).

    Returns:
        Initialized EasyOCR Reader instance.
    """
    global _reader
    if easyocr is None:
        raise RuntimeError("EasyOCR is not installed. Please install easyocr (pip install easyocr).")
    if _reader is None:
        langs = languages or ["en", "hi"]
        logger.info(f"Initializing EasyOCR reader with languages: {langs}")
        _reader = easyocr.Reader(langs, gpu=False)  # CPU for portability
        logger.info("EasyOCR reader initialized successfully")
    return _reader


def extract_text(
    image: np.ndarray,
    dpi: int = 300,
    languages: List[str] = None,
) -> List[OCRResult]:
    """
    Extract text from a preprocessed image using EasyOCR.

    Returns structured results with sanitized text, bounding boxes,
    confidence scores, and estimated font heights in both pixels and mm.

    Args:
        image: Preprocessed image as numpy array.
        dpi: Image DPI for pixel-to-mm conversion.
        languages: OCR language codes.

    Returns:
        List of OCRResult objects with sanitized text and measurements.
    """
    reader = get_reader(languages)

    # Run EasyOCR — returns list of (bbox, text, confidence)
    raw_results = reader.readtext(image, detail=1, paragraph=False)
    # If initial horizontal pass yielded sparse results (< 4 boxes), check rotated orientations
    if len(raw_results) < 4:
        try:
            rotated_results = reader.readtext(
                image, detail=1, paragraph=False, rotation_info=[90, 180, 270]
            )
            if len(rotated_results) > len(raw_results):
                raw_results = rotated_results
        except Exception as e:
            logger.debug(f"Rotation-aware OCR skipped: {e}")

    ocr_results: List[OCRResult] = []

    for bbox_points, text, confidence in raw_results:
        # Skip very low confidence results
        if confidence < 0.1:
            continue

        # Sanitize OCR text to prevent injection attacks
        sanitized_text = sanitize_ocr_text(text)
        if not sanitized_text.strip():
            continue

        # Parse bounding box points
        # EasyOCR returns: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
        # Order: top-left, top-right, bottom-right, bottom-left
        top_left = bbox_points[0]
        top_right = bbox_points[1]
        bottom_right = bbox_points[2]
        bottom_left = bbox_points[3]

        font_height_px = _letter_height_px(top_left, top_right, bottom_right, bottom_left, sanitized_text)

        # Convert pixel height to mm using DPI
        font_height_mm = pixel_to_mm(font_height_px, dpi)

        bbox = BoundingBox(
            top_left=[float(top_left[0]), float(top_left[1])],
            top_right=[float(top_right[0]), float(top_right[1])],
            bottom_right=[float(bottom_right[0]), float(bottom_right[1])],
            bottom_left=[float(bottom_left[0]), float(bottom_left[1])],
        )

        ocr_results.append(
            OCRResult(
                text=sanitized_text,
                bbox=bbox,
                confidence=round(float(confidence), 4),
                font_height_px=round(font_height_px, 2),
                font_height_mm=round(font_height_mm, 2) if font_height_mm else None,
            )
        )

    logger.info(f"OCR extracted {len(ocr_results)} text regions")
    return ocr_results


def _letter_height_px(top_left, top_right, bottom_right, bottom_left, text: str) -> float:
    """
    Letter height in pixels from an OCR box.

    Horizontal text: the box height. Sideways text (a line printed along a pack edge) gives a
    tall, narrow box whose WIDTH is the letter height; using its height would report the line
    length as a giant letter and could hide a Rule 7(2) font violation. A line is treated as
    sideways only when it has several characters and the box is clearly taller than wide, so a
    lone tall character such as "1" keeps its real height.
    """
    left_height = abs(float(bottom_left[1]) - float(top_left[1]))
    right_height = abs(float(bottom_right[1]) - float(top_right[1]))
    height = (left_height + right_height) / 2.0
    top_width = abs(float(top_right[0]) - float(top_left[0]))
    bottom_width = abs(float(bottom_right[0]) - float(bottom_left[0]))
    width = (top_width + bottom_width) / 2.0
    if len(text.strip()) >= 3 and height > 1.5 * width:
        return width
    return height


def pixel_to_mm(pixel_height: float, dpi: int) -> Optional[float]:
    """
    Convert pixel height to millimeters using DPI.

    Formula: height_mm = (pixel_height * 25.4) / DPI

    Args:
        pixel_height: Height in pixels.
        dpi: Dots per inch of the image.

    Returns:
        Height in millimeters, or None if DPI is invalid.
    """
    if dpi <= 0:
        return None
    return (pixel_height * 25.4) / dpi


def initialize_ocr(languages: List[str] = None):
    """
    Pre-initialize the OCR reader at application startup.
    This avoids cold-start latency on the first scan request.
    """
    logger.info("Pre-loading EasyOCR model...")
    get_reader(languages)
    logger.info("EasyOCR model pre-loaded successfully")
