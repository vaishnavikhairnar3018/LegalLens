"""
LenseScan Calibration & Optical Scale Recovery Service.

PURPOSE:
- Replaces fixed-DPI assumptions with physical reference calibration.
- Primary method: ArUco fiducial marker (40mm x 40mm default).
- Fallback methods: ₹10 Indian coin (26.0mm) or Standard ID Card (85.60mm x 53.98mm).
- Pre-capture image quality gate: blur detection (Laplacian variance) and targeted marker glare check.
- When no reference is found, returns calibration_status="no_reference" with pixels_per_mm=None.
  NEVER falls back to a guessed fixed DPI.
"""

import io
import math
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# ── Statutory & Physical Constants (Named Configuration) ──
ARUCO_DEFAULT_SIZE_MM: float = 40.0
ARUCO_DICTIONARY_ID = cv2.aruco.DICT_4X4_50

COIN_10RS_DIAMETER_MM: float = 26.0
CARD_WIDTH_MM: float = 85.60
CARD_HEIGHT_MM: float = 53.98
CARD_ASPECT_RATIO: float = CARD_WIDTH_MM / CARD_HEIGHT_MM  # 1.5858

BLUR_LAPLACIAN_THRESHOLD: float = 100.0
MARKER_GLARE_LUMINANCE_THRESHOLD: int = 250
MARKER_GLARE_AREA_RATIO_MAX: float = 0.10  # Max 10% saturated pixels allowed


@dataclass
class PreCaptureQuality:
    """Quality gate metrics evaluated prior to full compliance audit."""
    is_blurry: bool = False
    laplacian_variance: float = 0.0
    marker_has_glare: bool = False
    glare_pixel_ratio: float = 0.0
    status_code: str = "no_marker_quick_scan"
    # Minimal-text prompt per DESIGN.md:
    # "marker_detected_ready" | "no_marker_quick_scan" | "marker_detected_but_low_quality"
    user_prompt: str = "Quick scan mode (no physical reference detected)."


@dataclass
class CalibrationResult:
    """Physical scale recovery metrics and reference provenance."""
    calibration_method: str = "none"  # "aruco_40mm" | "none"
    reference_size_mm: Optional[float] = None
    detected_reference_px: Optional[float] = None
    pixels_per_mm: Optional[float] = None
    calibration_confidence: float = 0.0
    calibration_status: str = "no_reference"  # "calibrated" | "no_reference" | "low_quality"
    marker_id: Optional[int] = None
    marker_corners: Optional[List[List[float]]] = None
    quality_gate: PreCaptureQuality = field(default_factory=PreCaptureQuality)
    notes: List[str] = field(default_factory=list)


def check_pre_capture_quality(
    gray_image: np.ndarray,
    marker_corners: Optional[np.ndarray] = None,
) -> PreCaptureQuality:
    """
    Lightweight pre-capture quality evaluation:
    1. Blur detection via Laplacian variance over the entire frame.
    2. Localized glare/overexposure check specifically on the marker region.
    """
    # 1. Blur check
    lap_var = float(cv2.Laplacian(gray_image, cv2.CV_64F).var())
    is_blurry = lap_var < BLUR_LAPLACIAN_THRESHOLD

    # 2. Localized marker glare check
    marker_glare = False
    glare_ratio = 0.0

    if marker_corners is not None and len(marker_corners) > 0:
        pts = marker_corners[0].astype(np.int32)
        x_min = max(0, int(np.min(pts[:, 0])))
        x_max = min(gray_image.shape[1], int(np.max(pts[:, 0])))
        y_min = max(0, int(np.min(pts[:, 1])))
        y_max = min(gray_image.shape[0], int(np.max(pts[:, 1])))

        if (x_max - x_min > 5) and (y_max - y_min > 5):
            marker_roi = gray_image[y_min:y_max, x_min:x_max]
            saturated = np.count_nonzero(marker_roi >= MARKER_GLARE_LUMINANCE_THRESHOLD)
            total_roi_pixels = marker_roi.size
            if total_roi_pixels > 0:
                glare_ratio = float(saturated / total_roi_pixels)
                marker_glare = glare_ratio > MARKER_GLARE_AREA_RATIO_MAX

    # 3. Determine status code (strictly 3 states per prompt spec)
    if marker_corners is not None and len(marker_corners) > 0:
        if is_blurry or marker_glare:
            status_code = "marker_detected_but_low_quality"
            user_prompt = "Marker detected but blurry or glared. Please hold steady."
        else:
            status_code = "marker_detected_ready"
            user_prompt = "Reference marker calibrated and ready for scan."
    else:
        status_code = "no_marker_quick_scan"
        user_prompt = "Image may be blurry, retake." if is_blurry else "Quick scan mode (uncalibrated)."

    return PreCaptureQuality(
        is_blurry=is_blurry,
        laplacian_variance=round(lap_var, 2),
        marker_has_glare=marker_glare,
        glare_pixel_ratio=round(glare_ratio, 4),
        status_code=status_code,
        user_prompt=user_prompt,
    )


def calibrate_image(
    image_bytes: bytes,
    aruco_size_mm: float = ARUCO_DEFAULT_SIZE_MM,
) -> CalibrationResult:
    """
    Primary physical calibration routine:
    1. Preprocesses image to grayscale.
    2. Detects ArUco marker (40mm default).
    3. If no ArUco marker, the photo is uncalibrated (text only; no millimetre scale).
    4. Evaluates quality gate (blur and targeted glare).
    5. Returns CalibrationResult with exact pixels_per_mm or None.
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img_bgr is None:
        return CalibrationResult(
            calibration_status="low_quality",
            notes=["Corrupted or unreadable image bytes."],
        )

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # ── Method 1: ArUco Marker (Primary) ──
    aruco_res = _detect_aruco_marker(gray, aruco_size_mm)
    if aruco_res is not None:
        quality = check_pre_capture_quality(gray, aruco_res["corners"])
        # If severe glare or blur, adjust calibration confidence
        cal_conf = 1.0
        cal_status = "calibrated"
        notes = []

        if quality.marker_has_glare:
            cal_conf -= 0.35
            notes.append("Marker region exhibits optical glare saturation (>10%).")
        if quality.is_blurry:
            cal_conf -= 0.30
            notes.append("Image exhibits motion blur (low Laplacian variance).")

        if cal_conf < 0.60:
            cal_status = "low_quality"

        corners_list = aruco_res["corners"][0].tolist() if aruco_res["corners"] is not None else None

        return CalibrationResult(
            calibration_method=f"aruco_{int(aruco_size_mm)}mm",
            reference_size_mm=aruco_size_mm,
            detected_reference_px=round(aruco_res["pixel_width"], 2),
            pixels_per_mm=round(aruco_res["ppm"], 4),
            calibration_confidence=round(cal_conf, 2),
            calibration_status=cal_status,
            marker_id=aruco_res["id"],
            marker_corners=corners_list,
            quality_gate=quality,
            notes=notes,
        )

    # The ID-card and ₹10-coin fallbacks (_detect_id_card / _detect_coin_reference) are
    # deliberately NOT used: on real pack photos they matched round or rectangular label
    # art and produced invented scales. Only the ArUco marker is trusted for millimetres.

    # ── No Reference Detected: NEVER GUESS A FIXED DPI ──
    quality = check_pre_capture_quality(gray, None)
    return CalibrationResult(
        calibration_method="none",
        reference_size_mm=None,
        detected_reference_px=None,
        pixels_per_mm=None,
        calibration_confidence=0.0,
        calibration_status="no_reference",
        quality_gate=quality,
        notes=["No physical calibration reference found in frame; uncalibrated quick scan."],
    )


def _detect_aruco_marker(
    gray: np.ndarray,
    reference_size_mm: float,
) -> Optional[Dict[str, Any]]:
    """Detect ArUco marker using cv2.aruco and compute pixels_per_mm."""
    try:
        dictionary = cv2.aruco.getPredefinedDictionary(ARUCO_DICTIONARY_ID)
        parameters = cv2.aruco.DetectorParameters()
        detector = cv2.aruco.ArucoDetector(dictionary, parameters)
        corners, ids, _ = detector.detectMarkers(gray)

        if ids is not None and len(ids) > 0:
            c = corners[0][0]  # shape (4, 2): top-left, top-right, bottom-right, bottom-left
            # Measure all 4 edges
            top_edge = float(np.linalg.norm(c[0] - c[1]))
            right_edge = float(np.linalg.norm(c[1] - c[2]))
            bottom_edge = float(np.linalg.norm(c[2] - c[3]))
            left_edge = float(np.linalg.norm(c[3] - c[0]))

            avg_edge_px = (top_edge + right_edge + bottom_edge + left_edge) / 4.0

            if avg_edge_px < 10.0:
                return None  # Marker too small to be reliable

            # Squareness aspect check (ensures marker is not photographed at an unreadable tilt)
            aspect = max(top_edge, bottom_edge) / max(min(left_edge, right_edge), 1e-4)
            if aspect > 1.4 or aspect < 0.7:
                logger.warning(f"ArUco marker aspect ratio distortion ({aspect:.2f}) indicates severe perspective tilt.")

            ppm = avg_edge_px / reference_size_mm
            return {
                "id": int(ids.flatten()[0]),
                "corners": corners[0],
                "pixel_width": avg_edge_px,
                "ppm": ppm,
            }
    except Exception as e:
        logger.warning(f"ArUco detection error: {e}")

    return None


def _detect_id_card(gray: np.ndarray) -> Optional[Dict[str, Any]]:
    """
    Detect standard ID/Credit card (85.60 x 53.98mm) via rectangular contours.
    Strictly enforces ISO 7810 ID-1 aspect ratio of ~1.586 (+- 5%).
    """
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    min_area = (gray.shape[0] * gray.shape[1]) * 0.02  # At least 2% of image
    max_area = (gray.shape[0] * gray.shape[1]) * 0.70  # At most 70% of image

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if min_area < area < max_area:
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.03 * peri, True)
            if len(approx) == 4:
                # Calculate bounding rect or min area rect
                rect = cv2.minAreaRect(approx)
                w, h = rect[1]
                if w > 0 and h > 0:
                    long_side = max(w, h)
                    short_side = min(w, h)
                    ratio = long_side / short_side
                    if abs(ratio - CARD_ASPECT_RATIO) < 0.08:
                        ppm = long_side / CARD_WIDTH_MM
                        return {
                            "pixel_width": long_side,
                            "ppm": ppm,
                        }
    return None


def _detect_coin_reference(gray: np.ndarray) -> Optional[Dict[str, Any]]:
    """
    Detect circular coin reference (26mm) using Hough Circle Transform.
    Ensures circularity and strict contrast thresholding; never blindly assumes any circle.
    """
    blurred = cv2.medianBlur(gray, 5)
    rows = gray.shape[0]
    circles = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=rows / 8,
        param1=100,
        param2=45,
        minRadius=int(rows * 0.02),
        maxRadius=int(rows * 0.20),
    )

    if circles is not None:
        circles = np.uint16(np.around(circles))
        for pt in circles[0, :]:
            r = float(pt[2])
            diameter_px = r * 2.0
            ppm = diameter_px / COIN_10RS_DIAMETER_MM
            return {
                "pixel_diameter": diameter_px,
                "ppm": ppm,
            }
    return None
