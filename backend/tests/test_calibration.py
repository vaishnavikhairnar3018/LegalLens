"""
LenseScan Unit Tests — Physical Reference Calibration, Uncertainty,
Absence Classification, Prominence, and Cross-Panel Verification.
"""

import io
import math
import numpy as np
import cv2
from PIL import Image
import pytest

from app.schemas.scan import OCRResult, BoundingBox, DetectionStatus, DeclarationField
from app.services.calibration import (
    calibrate_image,
    check_pre_capture_quality,
    CalibrationResult,
    ARUCO_DEFAULT_SIZE_MM,
    ARUCO_DICTIONARY_ID,
)
from app.services.rule_engine import (
    validate_compliance,
    calculate_font_uncertainty,
    calculate_geometry_confidence,
    generate_summary,
)
from app.services.cross_panel import check_cross_panel_consistency
from app.services.declaration_classifier import classify_declarations
from pathlib import Path
from validation.evaluate_measurements import evaluate_ground_truth


def _create_synthetic_aruco_image(marker_size_px: int = 400, canvas_size: int = 800) -> bytes:
    """Generate a clean synthetic image with an ArUco DICT_4X4_50 marker simulating paper reflectance."""
    canvas = np.full((canvas_size, canvas_size, 3), 220, dtype=np.uint8)
    dictionary = cv2.aruco.getPredefinedDictionary(ARUCO_DICTIONARY_ID)
    marker_img = cv2.aruco.generateImageMarker(dictionary, 0, marker_size_px)
    marker_img[marker_img == 255] = 220
    marker_bgr = cv2.cvtColor(marker_img, cv2.COLOR_GRAY2BGR)

    # Place marker in center
    start_x = (canvas_size - marker_size_px) // 2
    start_y = (canvas_size - marker_size_px) // 2
    canvas[start_y:start_y + marker_size_px, start_x:start_x + marker_size_px] = marker_bgr

    _, buf = cv2.imencode(".png", canvas)
    return buf.tobytes()


def _dummy_bbox(top_left=(100.0, 100.0), width=200.0, height=50.0) -> BoundingBox:
    x, y = top_left
    return BoundingBox(
        top_left=[x, y],
        top_right=[x + width, y],
        bottom_right=[x + width, y + height],
        bottom_left=[x, y + height],
    )


def test_aruco_detection_math():
    """Verify that an ArUco 40mm marker with 400px edge yields 10.0 px/mm scale."""
    img_bytes = _create_synthetic_aruco_image(marker_size_px=400, canvas_size=800)
    result = calibrate_image(img_bytes, aruco_size_mm=40.0)

    assert result.calibration_status == "calibrated"
    assert result.calibration_method == "aruco_40mm"
    assert result.reference_size_mm == 40.0
    assert result.pixels_per_mm is not None
    # 400px / 40mm = 10.0 px/mm (allow small tolerance for subpixel antialiasing)
    assert abs(result.pixels_per_mm - 10.0) < 0.25
    assert result.calibration_confidence >= 0.70


FIXTURES = Path(__file__).parent / "fixtures"


def test_real_photo_without_marker_is_not_calibrated():
    """A real pack photo with no marker must stay uncalibrated: round or rectangular label art
    must never be mistaken for a coin or ID card (it previously came back as coin_26mm)."""
    result = calibrate_image((FIXTURES / "sargam_front_no_marker.jpg").read_bytes())
    assert result.calibration_method == "none"
    assert result.calibration_status == "no_reference"
    assert result.pixels_per_mm is None


def test_real_photo_with_marker_is_calibrated_by_aruco():
    """The same pack photographed with the printed 40 mm marker is calibrated from the marker."""
    result = calibrate_image((FIXTURES / "sargam_front_with_marker.jpg").read_bytes())
    assert result.calibration_method == "aruco_40mm"
    assert result.pixels_per_mm is not None and result.pixels_per_mm > 0


def test_uncalibrated_quick_scan_no_guessed_dpi():
    """Verify that when no reference marker exists, scale is None and never fixed to 300 DPI."""
    blank = np.full((600, 600, 3), 240, dtype=np.uint8)
    _, buf = cv2.imencode(".png", blank)
    raw_bytes = buf.tobytes()

    result = calibrate_image(raw_bytes)
    assert result.calibration_status == "no_reference"
    assert result.calibration_method == "none"
    assert result.pixels_per_mm is None
    assert result.reference_size_mm is None

    # Test passing this uncalibrated result into rule engine
    ocr_items = [
        OCRResult(text="MRP Rs. 100 (incl of taxes)", confidence=0.95, bbox=_dummy_bbox(), font_height_px=30.0),
        OCRResult(text="Net Qty: 500 g", confidence=0.95, bbox=_dummy_bbox(), font_height_px=25.0),
        OCRResult(text="Mfg Date: 01/2024", confidence=0.95, bbox=_dummy_bbox(), font_height_px=20.0),
        OCRResult(text="Mfg by Good Foods 400001", confidence=0.95, bbox=_dummy_bbox(), font_height_px=20.0),
    ]
    classified = classify_declarations(ocr_items)
    fields = validate_compliance(classified, ocr_items, calibration_result=result)

    mrp_field = next(f for f in fields if f.field_name == "mrp")
    assert mrp_field.font_height_mm is None
    assert mrp_field.font_review_required is True
    assert "Uncalibrated scan" in (mrp_field.font_review_reason or "")


def test_pre_capture_quality_blur_and_glare():
    """Verify pre-capture quality evaluation: blur detection and localized marker glare."""
    # 1. Severely blurred image
    gray_blur = np.full((400, 400), 128, dtype=np.uint8)
    q_blur = check_pre_capture_quality(gray_blur, None)
    assert q_blur.is_blurry is True
    assert q_blur.status_code == "no_marker_quick_scan"

    # 2. Synthetic sharp ArUco image
    sharp_bytes = _create_synthetic_aruco_image(marker_size_px=300, canvas_size=600)
    cal_sharp = calibrate_image(sharp_bytes)
    assert cal_sharp.quality_gate.status_code == "marker_detected_ready"
    assert cal_sharp.quality_gate.is_blurry is False
    assert cal_sharp.quality_gate.marker_has_glare is False

    # 3. Marker image with localized glare patch (>10% saturation at 255)
    img = cv2.imdecode(np.frombuffer(sharp_bytes, np.uint8), cv2.IMREAD_COLOR)
    # Paint a large specular glare rectangle in center of marker
    cv2.rectangle(img, (220, 220), (380, 380), (255, 255, 255), -1)
    _, glared_buf = cv2.imencode(".png", img)
    cal_glare = calibrate_image(glared_buf.tobytes())
    # Should flag low quality due to glare or unreadable marker
    assert cal_glare.quality_gate.marker_has_glare is True or cal_glare.quality_gate.status_code != "marker_detected_ready"


def test_rule_7_font_uncertainty_interval_logic():
    """
    Verify 3-way Rule 7(2) font-height decision logic with measurement uncertainty:
    Case A: Upper & lower bound strictly >= threshold -> Pass
    Case B: Upper bound < threshold -> Hard violation
    Case C: Interval straddles threshold -> Benefit-of-doubt pass + manual review required
    """
    cal = CalibrationResult(
        calibration_method="aruco_40mm",
        reference_size_mm=40.0,
        pixels_per_mm=10.0,  # 10 px/mm => 10px = 1mm
        calibration_confidence=1.0,
        calibration_status="calibrated",
    )

    # ── Case A: Clear Pass (30px = 3.0mm, min requirement = 2.0mm) ──
    ocr_pass = [
        OCRResult(text="Boundary 1", confidence=0.95, bbox=_dummy_bbox(), font_height_px=10.0),
        OCRResult(text="Boundary 2", confidence=0.95, bbox=_dummy_bbox(), font_height_px=10.0),
        OCRResult(text="Boundary 3", confidence=0.95, bbox=_dummy_bbox(), font_height_px=10.0),
        OCRResult(text="Net Qty: 500 g", confidence=0.95, bbox=_dummy_bbox(), font_height_px=30.0),
    ]
    class_pass = classify_declarations(ocr_pass)
    fields_pass = validate_compliance(class_pass, ocr_pass, default_font_min_mm=2.0, calibration_result=cal)
    net_pass = next(f for f in fields_pass if f.field_name == "net_quantity")
    assert net_pass.font_height_mm == 3.0
    assert net_pass.lower_bound_mm > 2.0
    assert net_pass.compliant is True
    assert net_pass.font_review_required is False

    # ── Case B: Definite Violation (8px = 0.8mm, min requirement = 2.0mm) ──
    ocr_fail = [
        OCRResult(text="Boundary 1", confidence=0.95, bbox=_dummy_bbox(), font_height_px=10.0),
        OCRResult(text="Boundary 2", confidence=0.95, bbox=_dummy_bbox(), font_height_px=10.0),
        OCRResult(text="Boundary 3", confidence=0.95, bbox=_dummy_bbox(), font_height_px=10.0),
        OCRResult(text="Net Qty: 500 g", confidence=0.95, bbox=_dummy_bbox(), font_height_px=8.0),
    ]
    class_fail = classify_declarations(ocr_fail)
    fields_fail = validate_compliance(class_fail, ocr_fail, default_font_min_mm=2.0, calibration_result=cal)
    net_fail = next(f for f in fields_fail if f.field_name == "net_quantity")
    assert net_fail.font_height_mm == 0.8
    assert net_fail.upper_bound_mm < 2.0
    assert net_fail.compliant is False
    assert any("FONT SIZE" in v for v in net_fail.violations)

    # ── Case C: Straddling Interval (19.5px = 1.95mm, min requirement = 2.0mm) ──
    # With ~5.4% uncertainty, upper bound is ~2.05mm, crossing 2.0mm.
    ocr_straddle = [
        OCRResult(text="Boundary 1", confidence=0.95, bbox=_dummy_bbox(), font_height_px=10.0),
        OCRResult(text="Boundary 2", confidence=0.95, bbox=_dummy_bbox(), font_height_px=10.0),
        OCRResult(text="Boundary 3", confidence=0.95, bbox=_dummy_bbox(), font_height_px=10.0),
        OCRResult(text="Net Qty: 500 g", confidence=0.95, bbox=_dummy_bbox(), font_height_px=19.5),
    ]
    class_straddle = classify_declarations(ocr_straddle)
    fields_straddle = validate_compliance(class_straddle, ocr_straddle, default_font_min_mm=2.0, calibration_result=cal)
    net_straddle = next(f for f in fields_straddle if f.field_name == "net_quantity")
    assert net_straddle.font_height_mm == 1.95
    assert net_straddle.lower_bound_mm < 2.0 <= net_straddle.upper_bound_mm
    # Statutory benefit-of-the-doubt: compliant remains True, manual review flagged
    assert net_straddle.compliant is True
    assert net_straddle.font_review_required is True
    assert "straddles Rule 7(2) minimum" in (net_straddle.font_review_reason or "")
    assert "Schedule II" not in (net_straddle.font_review_reason or "")


def test_not_detected_low_coverage_vs_confirmed_absent():
    """
    Verify distinction between low coverage (tight crop/partial photo)
    and confirmed absence (sufficient text anchors present).
    """
    # ── Scenario 1: Low coverage (<4 OCR regions) ──
    # Only 2 detections present; missing mandatory declarations should NOT trigger hard statutory citation
    sparse_ocr = [
        OCRResult(text="MRP Rs. 100 (incl of all taxes)", confidence=0.95, bbox=_dummy_bbox(), font_height_px=30.0),
        OCRResult(text="Net Qty: 500 g", confidence=0.95, bbox=_dummy_bbox(), font_height_px=25.0),
    ]
    class_sparse = classify_declarations(sparse_ocr)
    fields_sparse = validate_compliance(class_sparse, sparse_ocr)

    mfg_sparse = next(f for f in fields_sparse if f.field_name == "manufacturer_details")
    assert mfg_sparse.detected is False
    assert mfg_sparse.detection_status == DetectionStatus.NOT_DETECTED_LOW_COVERAGE
    assert mfg_sparse.coverage_review_required is True
    # Does not issue unverified missing declaration citation
    assert mfg_sparse.compliant is True
    assert len(mfg_sparse.violations) == 0

    # ── Scenario 2: High coverage (>=4 OCR regions) ──
    # Full label with 5 detections, but consumer_care is omitted
    dense_ocr = [
        OCRResult(text="Boundary Top", confidence=0.95, bbox=_dummy_bbox(), font_height_px=10.0),
        OCRResult(text="Boundary Bottom", confidence=0.95, bbox=_dummy_bbox(), font_height_px=10.0),
        OCRResult(text="MRP Rs. 100 (incl of all taxes)", confidence=0.95, bbox=_dummy_bbox(), font_height_px=30.0),
        OCRResult(text="Net Qty: 500 g", confidence=0.95, bbox=_dummy_bbox(), font_height_px=25.0),
        OCRResult(text="Mfg by Pure Foods Pvt Ltd 400001", confidence=0.95, bbox=_dummy_bbox(), font_height_px=20.0),
    ]
    class_dense = classify_declarations(dense_ocr)
    fields_dense = validate_compliance(class_dense, dense_ocr)

    care_dense = next(f for f in fields_dense if f.field_name == "consumer_care")
    assert care_dense.detected is False
    assert care_dense.detection_status == DetectionStatus.NOT_DETECTED_CONFIRMED_ABSENT
    assert care_dense.coverage_review_required is False
    assert care_dense.compliant is False
    assert any("MISSING" in v for v in care_dense.violations)


def test_relative_prominence_uncalibrated_ratio():
    """Verify intra-panel relative prominence warning when text height is <45% of panel median."""
    uncal = CalibrationResult(
        calibration_method="none",
        pixels_per_mm=None,
        calibration_status="no_reference",
    )
    # Panel median: (40 + 40 + 40 + 10) / ... median is 40.0px.
    # Net quantity is 12px -> ratio = 12 / 40 = 0.30 (< 0.45 threshold).
    ocr_items = [
        OCRResult(text="BRAND HEADER TITLE", confidence=0.95, bbox=_dummy_bbox(), font_height_px=40.0),
        OCRResult(text="DELICIOUS POTATO CHIPS", confidence=0.95, bbox=_dummy_bbox(), font_height_px=40.0),
        OCRResult(text="MRP Rs. 50 (incl of taxes)", confidence=0.95, bbox=_dummy_bbox(), font_height_px=40.0),
        OCRResult(text="Net Qty: 50 g", confidence=0.95, bbox=_dummy_bbox(), font_height_px=12.0),
    ]
    classified = classify_declarations(ocr_items)
    fields = validate_compliance(classified, ocr_items, calibration_result=uncal, relative_prominence_threshold=0.45)

    net_field = next(f for f in fields if f.field_name == "net_quantity")
    assert net_field.relative_prominence_flag is True
    assert "Relative prominence warning" in (net_field.relative_prominence_note or "")


def test_cross_panel_consistency_detection():
    """Verify multi-panel consistency service detects mismatched MRP and net quantities across panels."""
    panels = [
        {
            "panel_id": "front_pdp",
            "declarations": [
                DeclarationField(
                    field_name="mrp",
                    display_name="Maximum Retail Price",
                    detected=True,
                    value="Rs. 100.00",
                    compliant=True,
                ),
                DeclarationField(
                    field_name="net_quantity",
                    display_name="Net Quantity",
                    detected=True,
                    value="500 g",
                    compliant=True,
                ),
            ],
        },
        {
            "panel_id": "back_info_panel",
            "declarations": [
                DeclarationField(
                    field_name="mrp",
                    display_name="Maximum Retail Price",
                    detected=True,
                    value="Rs. 120.00",  # Contradicts front panel!
                    compliant=True,
                ),
                DeclarationField(
                    field_name="net_quantity",
                    display_name="Net Quantity",
                    detected=True,
                    value="500 g",  # Matches front panel
                    compliant=True,
                ),
            ],
        },
    ]

    mismatches = check_cross_panel_consistency(panels)
    assert len(mismatches) == 1
    mrp_mismatch = mismatches[0]
    assert mrp_mismatch["field_name"] == "mrp"
    assert "conflicting declarations" in mrp_mismatch["description"]
    assert len(mrp_mismatch["conflicts"]) == 2


def test_validation_evaluator_script():
    """Verify that evaluate_measurements.py correctly parses ground_truth.csv and computes error metrics."""
    gt_file = Path(__file__).resolve().parent.parent.parent / "validation" / "ground_truth.csv"
    results = evaluate_ground_truth(gt_file)

    assert results["status"] == "success"
    assert results["measured_records"] > 0
    assert results["overall_mae_mm"] < 0.25
    assert results["overall_rmse_mm"] < 0.25
    assert "aruco_40mm" in results["by_calibration_method"]
