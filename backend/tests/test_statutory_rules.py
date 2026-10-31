"""
Tests for Advanced Statutory Compliance Rules in LMPC Rules 2011
(citations verified against the Ministry of Consumer Affairs consolidated text
"Legal Metrology (Packaged Commodities) Rules, 2011 with all amendments"):
1. Rule 5 / Second Schedule standard pack sizes — omitted w.e.f. 01.10.2022 (GSR 779(E)),
   so a non-standard pack size must NOT raise a statutory violation.
2. Rule 12(6): Prohibited qualifying expressions ("approximate", "minimum", "not less than")
3. Rule 13(2) / 13(5): Unit of quantity below 1 kg / 1 L, and SI unit symbols
4. Rule 6(11): Unit Sale Price (USP) reconciliation (USP = MRP / Net Quantity)
5. Conflicting MRPs on one package — flagged for officer review, no statutory citation
6. Rule 6 sub-rule citations on MISSING declarations and Rule 8(1) placement
"""

import pytest
from app.services.rule_engine import (
    validate_prohibited_expressions,
    validate_unit_formatting,
    validate_usp_reconciliation,
    validate_duplicate_mrp,
    validate_compliance,
)
from app.schemas.scan import OCRResult, BoundingBox
from app.services.declaration_classifier import classify_declarations


def _dummy_bbox():
    return BoundingBox(
        top_left=[10.0, 10.0],
        top_right=[200.0, 10.0],
        bottom_right=[200.0, 40.0],
        bottom_left=[10.0, 40.0],
    )


def _bbox_at(x: float, y: float, w: float = 150.0, h: float = 30.0):
    return BoundingBox(
        top_left=[x, y],
        top_right=[x + w, y],
        bottom_right=[x + w, y + h],
        bottom_left=[x, y + h],
    )


# ── 1. Rule 5 / Second Schedule (omitted w.e.f. 01.10.2022) ──

def test_non_standard_pack_size_is_not_a_violation():
    """Rule 5 and the Second Schedule were omitted vide GSR 779(E); a 347g biscuit pack must not be cited."""
    ocr_items = [
        OCRResult(text="Parle-G Glucose Biscuits", confidence=0.95, bbox=_dummy_bbox(), font_height_px=40, font_height_mm=3.5),
        OCRResult(text="Net Weight: 347 g", confidence=0.94, bbox=_dummy_bbox(), font_height_px=25, font_height_mm=2.2),
        OCRResult(text="MRP Rs. 50.00 (Incl. of all taxes)", confidence=0.95, bbox=_dummy_bbox(), font_height_px=30, font_height_mm=2.5),
    ]
    classified = classify_declarations(ocr_items)
    fields = validate_compliance(classified, ocr_items, default_font_min_mm=1.0, commodity_category="biscuits")
    net_qty_field = next(f for f in fields if f.field_name == "net_quantity")
    assert not any(
        "Rule 5" in v or "Schedule II" in v or "NON-STANDARD" in v
        for v in net_qty_field.violations
    )
    assert net_qty_field.compliant is True


# ── 2. Rule 12(6) Prohibited Qualifying Expressions Tests ──

def test_rule_12_6_prohibited_terms_detected():
    """'Approximate', 'when packed', 'minimum', and 'not less than' violate Rule 12(6)."""
    violations = validate_prohibited_expressions("Net Wt. approx 500g")
    assert len(violations) > 0
    assert any("Rule 12(6)" in v and "approx" in v.lower() for v in violations)
    assert not any("Rule 13" in v for v in violations)

    violations_wp = validate_prohibited_expressions("Net Weight: 200g when packed")
    assert len(violations_wp) > 0
    assert any("when packed" in v.lower() for v in violations_wp)

    violations_min = validate_prohibited_expressions("Min Qty: 100 ml")
    assert len(violations_min) > 0
    assert any("min" in v.lower() for v in violations_min)


def test_rule_12_6_clean_declaration_passes():
    """Standard declarations without qualifying expressions must pass cleanly."""
    violations = validate_prohibited_expressions("Net Weight: 500 g")
    assert len(violations) == 0


# ── 3. Rule 13 Unit Formatting Tests ──

def test_rule_13_2_fractional_kg_violation():
    """Quantities under 1kg declared as '0.5 kg' violate Rule 13(2) (must be in grams)."""
    violations = validate_unit_formatting("0.5 kg")
    assert len(violations) > 0
    assert any("Rule 13(2)" in v and "grams" in v for v in violations)

    violations_liter = validate_unit_formatting("0.25 L")
    assert len(violations_liter) > 0
    assert any("Rule 13(2)" in v and "milliliters" in v for v in violations_liter)


def test_rule_13_5_non_standard_symbol_violation():
    """'gms', 'Kgs', 'ML', 'ltr' are not SI unit symbols (Rule 13(5))."""
    violations = validate_unit_formatting("500 gms")
    assert len(violations) > 0
    assert any("Rule 13(5)" in v for v in violations)
    assert not any("Schedule VI" in v for v in violations)


def test_rule_13_standard_units_pass():
    """Statutory symbols 'g', 'kg', 'ml', 'L' without fractions under 1000 pass."""
    assert len(validate_unit_formatting("500 g")) == 0
    assert len(validate_unit_formatting("1 kg")) == 0
    assert len(validate_unit_formatting("200 ml")) == 0
    assert len(validate_unit_formatting("1 L")) == 0


# ── 4. Rule 6(11) USP Reconciliation Tests ──

def test_usp_mathematical_reconciliation_pass():
    """MRP Rs. 100 for 200g gives expected USP of Rs. 0.50/g. Declared USP Rs 0.50/g passes."""
    is_valid, msg = validate_usp_reconciliation(
        mrp_text="MRP Rs. 100.00",
        net_qty_text="Net Qty: 200 g",
        usp_text="USP: Rs. 0.50 / g",
    )
    assert is_valid is True
    assert msg is None


def test_usp_mathematical_reconciliation_failure():
    """MRP Rs. 100 for 200g but declared USP is Rs. 0.85/g (>1.5% deviation) must fail under Rule 6(11)."""
    is_valid, msg = validate_usp_reconciliation(
        mrp_text="MRP Rs. 100.00",
        net_qty_text="Net Qty: 200 g",
        usp_text="USP: Rs. 0.85 / g",
    )
    assert is_valid is False
    assert "Rule 6(11)" in msg
    assert "6(1)(n)" not in msg
    assert "USP Reconciliation" in msg


# ── 5. Conflicting MRPs → officer review (no statutory citation) ──

def test_duplicate_mrp_conflict_detected_without_citation():
    """Two conflicting prices on the same package (Rs 45 vs Rs 65) are detected but not cited to a rule."""
    ocr_items = [
        OCRResult(text="MRP Rs. 45.00", confidence=0.95, bbox=_dummy_bbox(), font_height_px=20, font_height_mm=2.0),
        OCRResult(text="MRP Rs. 65.00", confidence=0.94, bbox=_dummy_bbox(), font_height_px=20, font_height_mm=2.0),
    ]
    is_conflict, msg = validate_duplicate_mrp(ocr_items)
    assert is_conflict is True
    assert "Rs. 45.00" in msg and "Rs. 65.00" in msg
    assert "Rule" not in msg


def test_duplicate_mrp_identical_or_single_passes():
    """A single MRP or identical price declarations pass without conflict."""
    ocr_items = [
        OCRResult(text="MRP Rs. 50.00", confidence=0.95, bbox=_dummy_bbox(), font_height_px=20, font_height_mm=2.0),
        OCRResult(text="MRP Rs. 50.00 (Incl. of all taxes)", confidence=0.92, bbox=_dummy_bbox(), font_height_px=20, font_height_mm=2.0),
    ]
    is_conflict, msg = validate_duplicate_mrp(ocr_items)
    assert is_conflict is False
    assert msg is None


def test_end_to_end_duplicate_mrp_is_review_not_violation():
    """Conflicting MRPs flag the MRP field for officer review instead of a hard statutory violation."""
    ocr_items = [
        OCRResult(text="MRP Rs. 45.00 (Incl. of all taxes)", confidence=0.95, bbox=_dummy_bbox(), font_height_px=30, font_height_mm=2.5),
        OCRResult(text="MRP Rs. 65.00", confidence=0.94, bbox=_dummy_bbox(), font_height_px=30, font_height_mm=2.5),
        OCRResult(text="Net Weight: 500 g", confidence=0.94, bbox=_dummy_bbox(), font_height_px=25, font_height_mm=2.2),
    ]
    classified = classify_declarations(ocr_items)
    fields = validate_compliance(classified, ocr_items, default_font_min_mm=1.0)
    mrp_field = next(f for f in fields if f.field_name == "mrp")
    assert mrp_field.price_review_required is True
    assert "Rs. 45.00" in (mrp_field.price_review_reason or "")
    assert not any("18(2)" in v or "DUAL MRP" in v for v in mrp_field.violations)


# ── 6. End-to-End citation checks ──

def test_end_to_end_rule_12_6_approx_violation():
    """An OCR scan containing 'approx 500g' triggers a Rule 12(6) qualifying term violation."""
    ocr_items = [
        OCRResult(text="Net Weight approx 500g", confidence=0.93, bbox=_dummy_bbox(), font_height_px=25, font_height_mm=2.2),
        OCRResult(text="MRP Rs. 100.00 (Incl. of all taxes)", confidence=0.95, bbox=_dummy_bbox(), font_height_px=30, font_height_mm=2.5),
    ]
    classified = classify_declarations(ocr_items)
    fields = validate_compliance(classified, ocr_items, default_font_min_mm=1.0)
    net_qty_field = next(f for f in fields if f.field_name == "net_quantity")
    assert net_qty_field.compliant is False
    assert any("Rule 12(6)" in v and "approximate" in v.lower() for v in net_qty_field.violations)


def test_rule_12_6_ignores_qualifiers_outside_the_quantity_line():
    """'Approximate values' in a nutrition table is not a qualifier on the net quantity (Maggi / Tata Salt photos)."""
    ocr_items = [
        OCRResult(text=t, confidence=0.95, bbox=_bbox_at(20.0, 20.0 + 60 * i), font_height_px=25, font_height_mm=2.0)
        for i, t in enumerate([
            "Net Weight: 500 g",
            "Nutritional information (approximate values) per 100 g",
            "Tasty", "Crunchy", "Fresh",
        ])
    ]
    fields = validate_compliance(classify_declarations(ocr_items), ocr_items, default_font_min_mm=1.0)
    net = next(f for f in fields if f.field_name == "net_quantity")
    assert not any("Rule 12(6)" in v for v in net.violations), net.violations


@pytest.mark.parametrize("label_text", ["300g", "Net Wt. 100 g", "NET QUANTITY: 1 kg", "500 ml"])
def test_net_quantity_number_and_unit_passes_format(label_text):
    """Rule 6(1)(c) asks for the quantity in a standard unit; it does not require the words
    'Net Wt'. A bare '300g' (as printed on the Sargam pack) must not get a FORMAT violation."""
    ocr_items = [
        OCRResult(text=t, confidence=0.95, bbox=_bbox_at(20.0, 20.0 + 60 * i), font_height_px=25, font_height_mm=2.0)
        for i, t in enumerate([label_text, "Tasty", "Crunchy", "Fresh", "Golden"])
    ]
    fields = validate_compliance(classify_declarations(ocr_items), ocr_items, default_font_min_mm=1.0)
    net = next(f for f in fields if f.field_name == "net_quantity")
    assert net.detected is True
    assert not any(v.startswith("FORMAT") for v in net.violations), net.violations


@pytest.mark.parametrize(
    "field_name, citation",
    [
        ("manufacturer_details", "Rule 6(1)(a)"),
        ("country_of_origin", "Rule 6(1)(aa)"),
        ("generic_name", "Rule 6(1)(b)"),
        ("net_quantity", "Rule 6(1)(c)"),
        ("manufacturing_date", "Rule 6(1)(d)"),
        ("best_before", "Rule 6(1)(da)"),
        ("mrp", "Rule 6(1)(e)"),
        ("consumer_care", "Rule 6(2)"),
    ],
)
def test_missing_declaration_cites_correct_rule_6_clause(field_name, citation):
    """With adequate coverage and no declarations, each MISSING message cites the gazette clause.
    Country of origin is only required on imported packages, so that case carries importer text."""
    words = ["Tasty", "Crunchy", "Fresh", "Golden", "Classic", "Delight"]
    if field_name == "country_of_origin":
        words.append("Imported by ABC Traders")
    ocr_items = [
        OCRResult(text=t, confidence=0.95, bbox=_bbox_at(20.0 + 10 * i, 20.0 + 60 * i), font_height_px=25, font_height_mm=2.0)
        for i, t in enumerate(words)
    ]
    classified = classify_declarations(ocr_items)
    fields = validate_compliance(classified, ocr_items, default_font_min_mm=1.0)
    field = next(f for f in fields if f.field_name == field_name)
    missing = [v for v in field.violations if v.startswith("MISSING")]
    assert missing, f"{field_name} was expected to be reported missing"
    assert f"under {citation} " in missing[0]


def _label(words):
    return [
        OCRResult(text=t, confidence=0.95, bbox=_bbox_at(20.0 + 10 * i, 20.0 + 60 * i), font_height_px=25, font_height_mm=2.0)
        for i, t in enumerate(words)
    ]


def test_country_of_origin_not_required_on_domestic_label():
    """Rule 6(1)(aa) applies to imported packages: an Indian label with no importer text and no
    foreign origin must not get MISSING (all 6 test products were flagged before this fix)."""
    ocr_items = _label(["Tasty", "Crunchy", "Manufactured & Packed by Ansari Masala Industries", "Fresh", "Golden"])
    fields = validate_compliance(classify_declarations(ocr_items), ocr_items, default_font_min_mm=1.0)
    origin = next(f for f in fields if f.field_name == "country_of_origin")
    assert origin.compliant is True
    assert origin.violations == []
    assert "imported" in (origin.note or "").lower()


@pytest.mark.parametrize("import_text", ["Imported by ABC Traders", "Importer: XYZ Foods Pvt Ltd"])
def test_country_of_origin_missing_on_imported_label(import_text):
    """Importer text makes the package imported, so an absent country of origin is a Rule 6(1)(aa) violation."""
    ocr_items = _label(["Tasty", "Crunchy", import_text, "Fresh", "Golden"])
    fields = validate_compliance(classify_declarations(ocr_items), ocr_items, default_font_min_mm=1.0)
    origin = next(f for f in fields if f.field_name == "country_of_origin")
    assert origin.compliant is False
    assert any(v.startswith("MISSING") and "Rule 6(1)(aa)" in v for v in origin.violations)


def test_mrp_with_colon_after_rupee_sign_is_detected_and_well_formed():
    """The Tower pouch prints 'MRP ₹ : 30/-' (colon after the ₹ sign); it must be read and pass FORMAT."""
    ocr_items = _label(["Tasty", "Crunchy", "MRP ₹ : 30/- (Incl. of all taxes)", "Fresh", "Golden"])
    declarations = classify_declarations(ocr_items)
    assert declarations["mrp"]["detected"] is True
    assert "30" in declarations["mrp"]["value"]
    mrp = next(f for f in validate_compliance(declarations, ocr_items, default_font_min_mm=1.0) if f.field_name == "mrp")
    assert not any(v.startswith("FORMAT") for v in mrp.violations), mrp.violations


def test_packing_date_with_month_name_keeps_the_full_date():
    """'Pkd. Date : 31 MAR 26' must be read as the whole date, not cut to '31'."""
    declarations = classify_declarations(_label(["Tasty", "Crunchy", "Pkd. Date : 31 MAR 26", "Fresh", "Golden"]))
    assert declarations["manufacturing_date"]["detected"] is True
    assert "31 MAR 26" in declarations["manufacturing_date"]["value"]


def test_pdp_placement_cites_rule_8_1():
    """MRP and net quantity far apart on a well-covered flat label cite Rule 8(1), not Rule 6(2)."""
    ocr_items = [
        OCRResult(text="MRP Rs. 50.00 (Incl. of all taxes)", confidence=0.95, bbox=_bbox_at(10.0, 10.0), font_height_px=30, font_height_mm=2.5),
        OCRResult(text="Classic", confidence=0.95, bbox=_bbox_at(400.0, 200.0), font_height_px=25, font_height_mm=2.0),
        OCRResult(text="Golden", confidence=0.95, bbox=_bbox_at(200.0, 400.0), font_height_px=25, font_height_mm=2.0),
        OCRResult(text="Crunchy", confidence=0.95, bbox=_bbox_at(600.0, 300.0), font_height_px=25, font_height_mm=2.0),
        OCRResult(text="Fresh", confidence=0.95, bbox=_bbox_at(300.0, 600.0), font_height_px=25, font_height_mm=2.0),
        OCRResult(text="Net Weight: 500 g", confidence=0.95, bbox=_bbox_at(800.0, 800.0), font_height_px=25, font_height_mm=2.2),
        OCRResult(text="Delight", confidence=0.95, bbox=_bbox_at(820.0, 900.0), font_height_px=25, font_height_mm=2.0),
    ]
    classified = classify_declarations(ocr_items)
    fields = validate_compliance(classified, ocr_items, default_font_min_mm=1.0)
    mrp_field = next(f for f in fields if f.field_name == "mrp")
    placement = [v for v in mrp_field.placement_violations if "Net Quantity" in v]
    assert placement, "expected an MRP / Net Quantity placement violation"
    assert "Rule 8(1)" in placement[0]
    assert "Rule 6(2)" not in placement[0]
