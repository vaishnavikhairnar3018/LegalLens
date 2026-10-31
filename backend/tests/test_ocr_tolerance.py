"""
Real OCR misreads from the 27 field photos (Acro Scanner Photos). Each test uses the exact text
EasyOCR produced, and each has a control case so tolerance never turns into accepting text that
is not on the label.
"""

from app.schemas.scan import BoundingBox, OCRResult
from app.services.declaration_classifier import classify_declarations
from app.services.rule_engine import validate_compliance


def _box(text, x, y, w=300.0, h=40.0, conf=0.8):
    return OCRResult(
        text=text,
        confidence=conf,
        bbox=BoundingBox(top_left=[x, y], top_right=[x + w, y], bottom_right=[x + w, y + h], bottom_left=[x, y + h]),
        font_height_px=h,
    )


FILLER = [_box(t, 40, 40 + 70 * i) for i, t in enumerate(["Chicken tikka masala", "Keep in cool & dry place", "Recipe inside"])]


def _field(items, name):
    fields = validate_compliance(classify_declarations(items), items, default_font_min_mm=1.0)
    return next(f for f in fields if f.field_name == name)


# ── "inclusive of all taxes" misread ──

def test_mrp_taxes_wording_read_as_laxes_is_recognised():
    """Tower photo 012629: '(Uncl , ol all laxes)' is the printed 'Incl. of all taxes'."""
    items = FILLER + [_box("MRP 30l-", 860, 1290), _box("(Uncl , ol all laxes)", 860, 1340)]
    mrp = _field(items, "mrp")
    assert mrp.detected
    assert not any(v.startswith("MRP TAXES") for v in mrp.violations), mrp.violations


def test_mrp_without_any_taxes_wording_is_still_flagged():
    items = FILLER + [_box("MRP 30l-", 860, 1290), _box("Batch No. B2330036D", 860, 1340)]
    mrp = _field(items, "mrp")
    assert any(v.startswith("MRP TAXES") for v in mrp.violations)


# ── consumer-care heading cut short ──

def test_customer_care_heading_cut_by_ocr_is_recognised():
    """Tower photo 012624: 'STOMER CARE NO: 02562-233815' is the printed 'CUSTOMER CARE NO:'."""
    items = FILLER + [_box("STOMER CARE NO: 02562-233815", 120, 1290)]
    care = _field(items, "consumer_care")
    assert care.detected
    assert "02562" in care.value or "233815" in care.value
    assert not any(v.startswith(("FORMAT", "MISSING")) for v in care.violations), care.violations


def test_the_word_care_alone_is_not_consumer_care():
    """'care at above address or call on' (same photo) is not a consumer-care declaration by itself."""
    items = FILLER + [_box("care at above address or call on", 120, 1240)]
    assert not _field(items, "consumer_care").detected


# ── date written in a separate box from its label ──

def test_packing_date_in_the_box_beside_its_label_is_found():
    """Tower photo 012629: 'Pkd Date' and '31 MAR 26' are separate boxes on neighbouring lines."""
    items = FILLER + [_box("Pkd Date", 863, 1519, w=200, h=40), _box("31 MAR 26", 1061, 1473, w=230, h=62)]
    date = _field(items, "manufacturing_date")
    assert date.detected
    assert "31 MAR 26" in date.value
    assert not any(v.startswith(("FORMAT", "MISSING")) for v in date.violations), date.violations


def test_use_by_date_in_the_box_beside_its_label_is_found():
    """Tata Salt photo 012345: 'use By:' and 'JUN/28' are separate boxes."""
    items = FILLER + [_box("use By:", 900, 1500, w=150, h=40), _box("JUN/28", 1080, 1498, w=140, h=42)]
    bb = _field(items, "best_before")
    assert bb.detected
    assert "JUN/28" in bb.value


def test_a_date_far_from_the_label_is_not_paired():
    """A date on the other side of the pack is not taken as the packing date."""
    items = FILLER + [_box("Pkd Date", 863, 1519, w=200, h=40), _box("31 MAR 26", 60, 300, w=230, h=40)]
    assert not _field(items, "manufacturing_date").detected


# ── letter O read instead of digit 0 ──

def test_letter_o_inside_a_quantity_is_read_as_zero():
    """Tower photo 012629: 'Net Weight : 10Og' is the printed 'Net Weight : 100g'."""
    items = FILLER + [_box("Net Weight : 10Og", 863, 1285)]
    nq = _field(items, "net_quantity")
    assert nq.detected
    assert "100g" in nq.value.replace(" ", "")
    assert not any(v.startswith("FORMAT") for v in nq.violations), nq.violations
