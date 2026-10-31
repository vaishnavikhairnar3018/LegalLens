"""
Rule 7(2) font-height checks using the area-of-PDP Table-I
(substituted vide GSR 629(E), w.e.f. 01.01.2018):

    PDP area A (cm2)     normal print   blown / formed / molded
    A <= 50              1.0 mm         2.0 mm
    50 < A <= 100        1.5 mm         3.0 mm
    100 < A <= 500       2.5 mm         4.0 mm
    500 < A <= 2500      4.0 mm         6.0 mm
    A > 2500             6.0 mm         6.0 mm

Tier upper edges are treated as inclusive (the more lenient reading).
"""

import pytest

from app.schemas.scan import OCRResult, BoundingBox
from app.services.calibration import CalibrationResult
from app.services.declaration_classifier import classify_declarations
from app.services.rule_engine import validate_compliance


def _bbox_at(x: float, y: float, w: float = 150.0, h: float = 30.0):
    return BoundingBox(
        top_left=[x, y],
        top_right=[x + w, y],
        bottom_right=[x + w, y + h],
        bottom_left=[x, y + h],
    )


def _calibrated(ppm: float = 10.0) -> CalibrationResult:
    return CalibrationResult(
        calibration_method="aruco_40mm",
        reference_size_mm=40.0,
        pixels_per_mm=ppm,
        calibration_confidence=1.0,
        calibration_status="calibrated",
    )


def _label(mrp_px: float = 50.0, care_px: float = 50.0):
    """A flat, well-covered label; at 10 px/mm, 50 px = 5.0 mm."""
    texts = [
        ("MRP Rs. 50.00 (Incl. of all taxes)", mrp_px),
        ("Net Weight: 200 g", 50.0),
        ("Customer Care: 1800-200-1122", care_px),
        ("Tasty", 50.0),
        ("Crunchy", 50.0),
        ("Fresh", 50.0),
    ]
    return [
        OCRResult(text=t, confidence=0.95, bbox=_bbox_at(20.0, 20.0 + 40 * i), font_height_px=px)
        for i, (t, px) in enumerate(texts)
    ]


def _field(fields, name):
    return next(f for f in fields if f.field_name == name)


@pytest.mark.parametrize(
    "area_cm2, expected_mm",
    [
        (30.0, 1.0),
        (50.0, 1.0),
        (50.5, 1.5),
        (100.0, 1.5),
        (100.5, 2.5),
        (500.0, 2.5),
        (2500.0, 4.0),
        (2600.0, 6.0),
    ],
)
def test_required_font_height_follows_pdp_area_table(area_cm2, expected_mm):
    ocr = _label()
    fields = validate_compliance(classify_declarations(ocr), ocr, calibration_result=_calibrated(), pdp_area_cm2=area_cm2)
    mrp = _field(fields, "mrp")
    assert mrp.required_font_height_mm == expected_mm
    assert mrp.pdp_area_cm2 == area_cm2


def test_text_below_area_minimum_is_a_violation():
    """PDP 300 cm2 needs 2.5 mm; MRP measured at 1.5 mm (15 px at 10 px/mm) is a hard violation."""
    ocr = _label(mrp_px=15.0)
    fields = validate_compliance(classify_declarations(ocr), ocr, calibration_result=_calibrated(), pdp_area_cm2=300.0)
    mrp = _field(fields, "mrp")
    assert mrp.compliant is False
    font = [v for v in mrp.violations if v.startswith("FONT SIZE")]
    assert font and "Rule 7(2)" in font[0] and "2.5mm" in font[0]


def test_missing_pdp_area_is_review_never_violation():
    """Calibrated scan without a PDP area: even tiny text is flagged for review, not cited."""
    ocr = _label(mrp_px=8.0)
    fields = validate_compliance(classify_declarations(ocr), ocr, calibration_result=_calibrated())
    mrp = _field(fields, "mrp")
    assert mrp.font_height_mm == 0.8
    assert mrp.required_font_height_mm is None
    assert mrp.font_review_required is True
    assert "PDP area" in (mrp.font_review_reason or "")
    assert not any(v.startswith("FONT SIZE") for v in mrp.violations)


def test_font_check_covers_all_rule_6_declarations():
    """Rule 7(2) applies to every declaration, e.g. consumer care at 1.0 mm on a 300 cm2 PDP fails."""
    ocr = _label(care_px=10.0)
    fields = validate_compliance(classify_declarations(ocr), ocr, calibration_result=_calibrated(), pdp_area_cm2=300.0)
    care = _field(fields, "consumer_care")
    assert care.required_font_height_mm == 2.5
    assert any(v.startswith("FONT SIZE") for v in care.violations)
    assert care.compliant is False


def test_uncalibrated_scan_stays_review_even_with_area():
    """Without a physical reference the mm height is unknown, so the area alone cannot produce a violation."""
    ocr = _label(mrp_px=8.0)
    uncal = CalibrationResult(calibration_method="none", pixels_per_mm=None, calibration_status="no_reference")
    fields = validate_compliance(classify_declarations(ocr), ocr, calibration_result=uncal, pdp_area_cm2=300.0)
    mrp = _field(fields, "mrp")
    assert mrp.font_review_required is True
    assert "Uncalibrated scan" in (mrp.font_review_reason or "")
    assert not any(v.startswith("FONT SIZE") for v in mrp.violations)
