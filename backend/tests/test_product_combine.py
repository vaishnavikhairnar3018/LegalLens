"""
Product inspection from several photos: a declaration is taken from the photo with the
40 mm marker when it appears there (so its font size is measured); otherwise from a photo
without the marker, and its font size then goes to officer review. A declaration is only
"missing" if no photo shows it.
"""

from app.schemas.scan import DeclarationField, DetectionStatus
from app.services.product_combine import PhotoResult, combine_photo_results


def _field(name, detected, *, value=None, compliant=True, violations=None, font_mm=None,
           font_review=False, font_reason=None, confidence=0.9,
           status=DetectionStatus.DETECTED, coverage_review=False):
    return DeclarationField(
        field_name=name,
        display_name=name.replace("_", " ").title(),
        detected=detected,
        detection_status=status,
        value=value,
        compliant=compliant,
        violations=violations or [],
        font_height_mm=font_mm,
        font_review_required=font_review,
        font_review_reason=font_reason,
        confidence=confidence if detected else None,
        coverage_review_required=coverage_review,
    )


def _by_name(fields):
    return {f.field_name: f for f in fields}


def test_text_only_photo_supplies_declaration_and_font_goes_to_review():
    clean = PhotoResult("clean.jpg", calibrated=False, fields=[
        _field("mrp", True, value="MRP Rs. 10.00", font_review=True, font_reason="Uncalibrated scan"),
    ])
    marker = PhotoResult("marker.jpg", calibrated=True, fields=[
        _field("mrp", False, compliant=False, status=DetectionStatus.NOT_DETECTED_CONFIRMED_ABSENT,
               violations=["MISSING: 'Mrp' is a mandatory declaration under Rule 6(1)(e) but was not detected on the label."]),
    ])
    mrp = _by_name(combine_photo_results([clean, marker]))["mrp"]

    assert mrp.detected is True
    assert mrp.value == "MRP Rs. 10.00"
    assert mrp.compliant is True
    assert not any(v.startswith("MISSING") for v in mrp.violations)
    assert mrp.font_height_mm is None
    assert mrp.font_review_required is True
    assert "without the marker" in (mrp.font_review_reason or "")


def test_text_from_clean_photo_font_from_marker_photo():
    """The clean photo supplies the declaration text; the marker photo only supplies the font measurement."""
    clean = PhotoResult("clean.jpg", calibrated=False, fields=[
        _field("net_quantity", True, value="Net Wt 12 g", confidence=0.97, font_review=True, font_reason="Uncalibrated scan"),
    ])
    marker = PhotoResult("marker.jpg", calibrated=True, fields=[
        _field("net_quantity", True, value="Net Wt l2g", confidence=0.80, compliant=False, font_mm=0.7,
               violations=["FONT SIZE: Measured font height 0.70mm is below minimum required 1.0mm per LMPC Rule 7(2)."]),
    ])
    nq = _by_name(combine_photo_results([clean, marker]))["net_quantity"]

    assert nq.value == "Net Wt 12 g"  # text from the clean photo, not the marker photo
    assert nq.font_height_mm == 0.7  # measurement from the marker photo
    assert nq.compliant is False
    assert any(v.startswith("FONT SIZE") for v in nq.violations)


def test_marker_photo_text_is_not_used_when_a_clean_photo_has_the_declaration():
    clean = PhotoResult("clean.jpg", calibrated=False, fields=[
        _field("mrp", True, value="MRP Rs. 30.00", compliant=True, font_review=True, font_reason="Uncalibrated scan"),
    ])
    marker = PhotoResult("marker.jpg", calibrated=True, fields=[
        _field("mrp", True, value="MRP 00", compliant=False, font_mm=3.6,
               violations=["FORMAT: Detected value 'MRP 00' does not match the expected format."]),
    ])
    mrp = _by_name(combine_photo_results([clean, marker]))["mrp"]

    assert mrp.value == "MRP Rs. 30.00"
    assert not any(v.startswith("FORMAT") for v in mrp.violations)  # the marker photo's misread text is ignored
    assert mrp.compliant is True
    assert mrp.font_height_mm == 3.6


def test_declaration_seen_only_in_marker_photo_still_counts():
    """If no clean photo shows a declaration but a marker photo does, it is present (not MISSING)."""
    clean = PhotoResult("clean.jpg", calibrated=False, fields=[
        _field("best_before", False, compliant=False, status=DetectionStatus.NOT_DETECTED_CONFIRMED_ABSENT,
               violations=["MISSING: 'Best Before' ..."]),
    ])
    marker = PhotoResult("marker.jpg", calibrated=True, fields=[
        _field("best_before", True, value="Best before 6 months", font_mm=2.0),
    ])
    bb = _by_name(combine_photo_results([clean, marker]))["best_before"]

    assert bb.detected is True
    assert bb.value == "Best before 6 months"
    assert not any(v.startswith("MISSING") for v in bb.violations)


def test_missing_from_every_photo_is_a_violation():
    a = PhotoResult("a.jpg", calibrated=False, fields=[
        _field("best_before", False, compliant=False, status=DetectionStatus.NOT_DETECTED_CONFIRMED_ABSENT,
               violations=["MISSING: 'Best Before' ... Rule 6(1)(da) ..."]),
    ])
    b = PhotoResult("b.jpg", calibrated=True, fields=[
        _field("best_before", False, compliant=False, status=DetectionStatus.NOT_DETECTED_CONFIRMED_ABSENT,
               violations=["MISSING: 'Best Before' ... Rule 6(1)(da) ..."]),
    ])
    bb = _by_name(combine_photo_results([a, b]))["best_before"]

    assert bb.detected is False
    assert bb.compliant is False
    assert any(v.startswith("MISSING") for v in bb.violations)


def test_low_coverage_everywhere_stays_a_review_not_a_violation():
    a = PhotoResult("a.jpg", calibrated=False, fields=[
        _field("consumer_care", False, compliant=True, status=DetectionStatus.NOT_DETECTED_LOW_COVERAGE, coverage_review=True),
    ])
    b = PhotoResult("b.jpg", calibrated=True, fields=[
        _field("consumer_care", False, compliant=True, status=DetectionStatus.NOT_DETECTED_LOW_COVERAGE, coverage_review=True),
    ])
    cc = _by_name(combine_photo_results([a, b]))["consumer_care"]

    assert cc.detected is False
    assert cc.compliant is True
    assert cc.coverage_review_required is True
    assert not cc.violations


def test_one_confirmed_absence_outweighs_low_coverage_elsewhere():
    """If any photo had enough text to confirm the declaration is absent, the absence stands."""
    sparse = PhotoResult("sparse.jpg", calibrated=False, fields=[
        _field("manufacturer_details", False, status=DetectionStatus.NOT_DETECTED_LOW_COVERAGE, coverage_review=True),
    ])
    full = PhotoResult("full.jpg", calibrated=True, fields=[
        _field("manufacturer_details", False, compliant=False, status=DetectionStatus.NOT_DETECTED_CONFIRMED_ABSENT,
               violations=["MISSING: 'Manufacturer' ... Rule 6(1)(a) ..."]),
    ])
    md = _by_name(combine_photo_results([sparse, full]))["manufacturer_details"]

    assert md.compliant is False
    assert md.coverage_review_required is False


def test_importer_text_on_any_photo_makes_missing_origin_a_violation():
    """The front photo has no importer text (origin not required there), the back photo says
    'Imported by' (origin required): the product is imported, so the absence is a violation."""
    front = PhotoResult("front.jpg", calibrated=False, fields=[
        _field("country_of_origin", False, compliant=True, status=DetectionStatus.NOT_DETECTED_CONFIRMED_ABSENT),
    ])
    back = PhotoResult("back.jpg", calibrated=False, fields=[
        _field("country_of_origin", False, compliant=False, status=DetectionStatus.NOT_DETECTED_CONFIRMED_ABSENT,
               violations=["MISSING: 'Country of Origin' ... Rule 6(1)(aa) ..."]),
    ])
    origin = _by_name(combine_photo_results([front, back]))["country_of_origin"]

    assert origin.compliant is False
    assert any(v.startswith("MISSING") for v in origin.violations)


def test_field_order_follows_first_photo():
    a = PhotoResult("a.jpg", calibrated=False, fields=[_field("mrp", True, value="MRP 10"), _field("net_quantity", True, value="12 g")])
    b = PhotoResult("b.jpg", calibrated=True, fields=[_field("mrp", False), _field("net_quantity", False)])
    assert [f.field_name for f in combine_photo_results([a, b])] == ["mrp", "net_quantity"]
