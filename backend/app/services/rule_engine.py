"""
LenseScan Rule Engine.
Validates classified declarations against LMPC Rules 2011.
Loads rules from JSON configuration and produces compliance reports.
"""

import json
import re
import math
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import numpy as np

from app.schemas.scan import DeclarationField, OCRResult, DetectionStatus
from app.services.calibration import CalibrationResult

logger = logging.getLogger(__name__)

# Rules loaded once at module level
_rules_config: Optional[Dict[str, Any]] = None
RULES_FILE = Path(__file__).parent.parent.parent / "rules" / "lmpc_rules.json"


def load_rules() -> Dict[str, Any]:
    """
    Load LMPC rules from JSON configuration file.
    Cached after first load.
    """
    global _rules_config
    if _rules_config is None:
        logger.info(f"Loading LMPC rules from {RULES_FILE}")
        with open(RULES_FILE, "r", encoding="utf-8") as f:
            _rules_config = json.load(f)
        logger.info(
            f"Loaded {len(_rules_config.get('rules', []))} rules "
            f"(v{_rules_config.get('metadata', {}).get('version', 'unknown')})"
        )
    return _rules_config


def calculate_geometry_confidence(
    ocr_results: List[OCRResult],
    bbox_centers: Dict[str, List[float]],
) -> float:
    """
    Evaluate the geometric stability and planarity of the scanned label.
    Detects non-planar, curved, or skewed conditions (e.g. bottles, pouches, angled camera shots)
    where automated placement coordinates cannot be certified with high certainty.
    """
    if not ocr_results:
        return 0.0

    confidence = 1.0

    # 1. Spatial anchor density: need at least 4 detections across the label to define a panel coordinate system
    num_boxes = len(ocr_results)
    if num_boxes < 4:
        confidence -= 0.40
    elif num_boxes < 6:
        confidence -= 0.15

    # 2. Average OCR detection confidence of detections
    confidences = [
        res.confidence for res in ocr_results
        if hasattr(res, "confidence") and res.confidence is not None
    ]
    if confidences:
        avg_conf = sum(confidences) / len(confidences)
        if avg_conf < 0.65:
            confidence -= 0.35
        elif avg_conf < 0.75:
            confidence -= 0.15

    # 3. Coordinate span & aspect ratio distortion
    all_x, all_y = [], []
    for entry in ocr_results:
        if hasattr(entry, "bbox") and entry.bbox:
            for pt in [
                entry.bbox.top_left,
                entry.bbox.top_right,
                entry.bbox.bottom_right,
                entry.bbox.bottom_left,
            ]:
                all_x.append(pt[0])
                all_y.append(pt[1])

    if all_x and all_y:
        span_x = max(all_x) - min(all_x)
        span_y = max(all_y) - min(all_y)
        aspect = span_x / max(span_y, 1.0)
        # Extreme aspect ratio typical of cylindrical bottle wrap-around scans
        if aspect > 5.0 or aspect < 0.20:
            confidence -= 0.25

    return max(0.0, min(1.0, confidence))


def calculate_font_uncertainty(
    font_height_mm: float,
    calibration_method: Optional[str],
    geometry_confidence: float,
) -> Tuple[float, float, float]:
    """
    Computes measurement uncertainty interval [lower_bound, upper_bound] and uncertainty delta.

    Formula:
        Delta_h = h * sqrt((eps_ref)^2 + (eps_ocr)^2 + (eps_geom)^2)
        - eps_ref: 0.02 (ArUco), 0.04 (Card), 0.05 (Coin)
        - eps_ocr: 0.05 (Bounding box edge estimation)
        - eps_geom: (1.0 - geometry_confidence) * 0.15 (Non-planar distortion)
    """
    method = (calibration_method or "").lower()
    if "aruco" in method:
        eps_ref = 0.02
    elif "card" in method:
        eps_ref = 0.04
    elif "coin" in method:
        eps_ref = 0.05
    else:
        eps_ref = 0.02

    eps_ocr = 0.05
    eps_geom = max(0.0, (1.0 - geometry_confidence) * 0.15)

    rel_unc = math.sqrt(eps_ref**2 + eps_ocr**2 + eps_geom**2)
    unc_mm = font_height_mm * rel_unc
    lower_mm = max(0.0, font_height_mm - unc_mm)
    upper_mm = font_height_mm + unc_mm
    return round(unc_mm, 2), round(lower_mm, 2), round(upper_mm, 2)


# ──────────────────────────────────────────────────────────
# Advanced Statutory Validation Functions (LMPC Rules 2011)
# ──────────────────────────────────────────────────────────

def required_font_height_for_area(
    pdp_area_cm2: Optional[float],
    blown_formed_molded: bool = False,
) -> Optional[float]:
    """
    Minimum height (mm) of numerals and letters per Rule 7(2) Table-I, by PDP area in cm².
    Tier upper edges are inclusive. Returns None when the area is unknown.
    """
    if pdp_area_cm2 is None or pdp_area_cm2 <= 0:
        return None
    column = "blown_formed_molded" if blown_formed_molded else "normal_print"
    for tier in load_rules()["font_size_schedule"]["rule_7_2_table_i"]:
        max_area = tier["max_pdp_area_cm2"]
        if max_area is None or pdp_area_cm2 <= max_area:
            return float(tier[column])
    return None


# NOTE: Rule 5 and the Second Schedule (standard pack sizes) were omitted vide
# GSR 779(E) dated 02.11.2021, w.e.f. 01.10.2022. No pack-size check is performed.


def validate_prohibited_expressions(net_qty_text: str, full_ocr_text: str = "") -> List[str]:
    """
    Validate that quantity declarations do not contain qualifying terms prohibited under Rule 12(6).
    """
    if not net_qty_text:
        return []

    violations = []
    PROHIBITED_PATTERNS = [
        (re.compile(r"\bapprox(?:imate|imately)?\b", re.IGNORECASE), "approximate"),
        (re.compile(r"\bwhen\s*packed\b", re.IGNORECASE), "when packed"),
        (re.compile(r"\bmin(?:imum)?\b", re.IGNORECASE), "minimum"),
        (re.compile(r"\bnot\s*less\s*than\b", re.IGNORECASE), "not less than"),
        (re.compile(r"\bapproximate\s*weight\b", re.IGNORECASE), "approximate weight"),
    ]

    for pattern, term in PROHIBITED_PATTERNS:
        if pattern.search(net_qty_text) or (full_ocr_text and pattern.search(full_ocr_text)):
            violations.append(
                f"Rule 12(6) Qualifying Term: Quantity declaration contains prohibited qualifying term '{term}'. "
                f"Rule 12(6) of LMPC Rules 2011 forbids words or expressions likely to create an exaggerated, "
                f"misleading or inadequate impression as to quantity (e.g. 'minimum', 'not less than', 'approximately')."
            )

    return violations


def validate_unit_formatting(net_qty_text: str) -> List[str]:
    """
    Validate measurement unit symbols and fractional representation per Rule 13(2) and Rule 13(5).
    """
    if not net_qty_text:
        return []

    violations = []

    # Rule 13(2) Quantities less than 1kg / 1L
    if re.search(r"\b0\.\d+\s*(?:kg|kgs|Kgs)\b", net_qty_text, re.IGNORECASE):
        violations.append(
            "Rule 13(2) Fractional Unit: Quantities less than 1 kilogram must be declared in grams "
            "(e.g. '500 g', not '0.5 kg')."
        )
    if re.search(r"\b0\.\d+\s*(?:l|L|ltr|litres?)\b", net_qty_text, re.IGNORECASE):
        violations.append(
            "Rule 13(2) Fractional Unit: Quantities less than 1 liter must be declared in milliliters "
            "(e.g. '500 ml', not '0.5 L')."
        )

    # Rule 13(5) non-SI unit symbols
    NON_STANDARD_SYMBOLS = re.compile(
        r"\b(gm|gms|gms\.|gm\.|Kgs|kgs|KG|ML|ltr|ltrs|ltr\.|litres|litre)\b"
    )
    m = NON_STANDARD_SYMBOLS.search(net_qty_text)
    if m:
        symbol = m.group(1)
        violations.append(
            f"Rule 13(5) Unit Symbol: Non-standard unit symbol '{symbol}' used. "
            f"Rule 13(5) requires International System of Units; SI symbols are 'g' for gram, "
            f"'kg' for kilogram, 'ml'/'mL' for milliliter, and 'l'/'L' for liter."
        )

    return violations


def validate_usp_reconciliation(
    mrp_text: str,
    net_qty_text: str,
    usp_text: str,
) -> Tuple[bool, Optional[str]]:
    """
    Validate that declared Unit Sale Price mathematically reconciles with MRP / Net Quantity
    within a 1.5% tolerance threshold per Rule 6(11).
    """
    if not mrp_text or not net_qty_text or not usp_text:
        return True, None

    # 1. Extract numeric MRP
    mrp_match = re.search(r"[\d,]+(?:\.\d+)?", mrp_text.replace("Rs.", "").replace("₹", ""))
    if not mrp_match:
        return True, None
    mrp_val = float(mrp_match.group(0).replace(",", ""))

    # 2. Extract numeric Net Quantity & Unit
    qty_match = re.search(r"([\d,]+(?:\.\d+)?)\s*([a-zA-Z]+)", net_qty_text)
    if not qty_match:
        return True, None
    qty_val = float(qty_match.group(1).replace(",", ""))
    qty_unit = qty_match.group(2).lower()

    # 3. Extract declared USP and base
    usp_clean = usp_text.replace("Rs.", "").replace("₹", "").replace("USP", "").replace(":", "")
    usp_match = re.search(r"([\d,]+(?:\.\d+)?)\s*(?:/|per)\s*([\d.]*)\s*([a-zA-Z]+)", usp_clean)
    if not usp_match:
        usp_match = re.search(r"([\d,]+(?:\.\d+)?)\s*(?:/|per)\s*([a-zA-Z]+)", usp_clean)
        if not usp_match:
            return True, None
        decl_usp_val = float(usp_match.group(1).replace(",", ""))
        usp_unit_qty = 1.0
        usp_unit = usp_match.group(2).lower()
    else:
        decl_usp_val = float(usp_match.group(1).replace(",", ""))
        unit_qty_str = usp_match.group(2).strip()
        usp_unit_qty = float(unit_qty_str) if unit_qty_str else 1.0
        usp_unit = usp_match.group(3).lower()

    if qty_unit in ["kg", "kgs", "l", "ltr", "litre"]:
        qty_in_base = qty_val * 1000.0
    else:
        qty_in_base = qty_val

    if usp_unit in ["kg", "kgs", "l", "ltr", "litre"]:
        usp_base_grams = usp_unit_qty * 1000.0
    else:
        usp_base_grams = usp_unit_qty

    if qty_in_base <= 0:
        return True, None

    expected_usp = (mrp_val / qty_in_base) * usp_base_grams

    deviation = abs(decl_usp_val - expected_usp) / expected_usp
    if deviation > 0.015:
        pct = deviation * 100.0
        return (
            False,
            f"Rule 6(11) USP Reconciliation: Declared Unit Sale Price ({usp_text.strip()}) does not "
            f"mathematically reconcile with MRP ({mrp_text.strip()}) / Net Quantity ({net_qty_text.strip()}). "
            f"Expected USP is Rs. {expected_usp:.2f} (deviation: {pct:.1f}%)."
        )

    return True, None


def validate_duplicate_mrp(ocr_results: List[OCRResult]) -> Tuple[bool, Optional[str]]:
    """
    Detect conflicting MRP declarations on the same package.

    No single LMPC sub-rule maps cleanly to this case (Rule 18(2) concerns sale above
    MRP; Rule 18(2A) concerns different MRPs on identical commodities), so the result
    is surfaced for officer review rather than cited as a statutory violation.
    """
    if not ocr_results:
        return False, None

    mrp_pattern = re.compile(
        r"(?:M\.?\s*R\.?\s*P\.?|Maximum\s*Retail\s*Price|Retail\s*Price)\s*[:\-?]?\s*(?:[₹\?]|Rs\.?|INR)?\s*[:\-]?\s*([\d,]+(?:\.\d{1,2})?)",
        re.IGNORECASE,
    )

    found_prices = set()
    for res in ocr_results:
        m = mrp_pattern.search(res.text)
        if m:
            try:
                price = float(m.group(1).replace(",", ""))
                found_prices.add(price)
            except ValueError:
                continue

    if len(found_prices) > 1:
        prices_list = sorted(list(found_prices))
        min_p = prices_list[0]
        max_p = prices_list[-1]
        if (max_p - min_p) / min_p > 0.05:
            str_prices = ", ".join(f"Rs. {p:.2f}" for p in prices_list)
            return (
                True,
                f"Conflicting retail prices detected on package ({str_prices}). "
                f"Officer must verify which MRP applies and whether a permitted lower-MRP sticker was used."
            )

    return False, None


_IMPORTER_TEXT = re.compile(r"\bImport(?:ed|er)\b", re.IGNORECASE)
_FOREIGN_ORIGIN = re.compile(
    r"(?:Made\s*in|Product\s*of|Country\s*of\s*Origin)\s*[:\-]?\s*(?!India\b|Bharat\b)[A-Za-z]{3,}",
    re.IGNORECASE,
)

NOT_IMPORTED_NOTE = (
    "Not required: country of origin applies to imported packages (Rule 6(1)(aa)), "
    "and no importer details or foreign origin were found on this label."
)


def is_imported_package(ocr_results: List[OCRResult]) -> bool:
    """A package counts as imported when the label names an importer ('Imported by', 'Importer')
    or gives a country of origin other than India."""
    text = " ".join(r.text for r in ocr_results if hasattr(r, "text"))
    return bool(_IMPORTER_TEXT.search(text) or _FOREIGN_ORIGIN.search(text))


def validate_compliance(
    declarations: Dict[str, Any],
    ocr_results: List[OCRResult],
    default_font_min_mm: float = 1.0,
    calibration_result: Optional[CalibrationResult] = None,
    relative_prominence_threshold: float = 0.45,
    commodity_category: Optional[str] = None,
    pdp_area_cm2: Optional[float] = None,
) -> List[DeclarationField]:
    """
    Validate classified declarations against LMPC rules.

    Checks:
    1. Presence — Is each mandatory declaration detected?
    2. Format — Does the value match legal requirements (e.g., MRP format, PIN code)?
    3. Font size — Does the font height meet LMPC minimums (with physical calibration + uncertainty)?
    4. Special requirements (e.g., MRP must include taxes text)
    5. Placement — Rule 8(1) Principal Display Panel (PDP) grouping and margin checks
    6. Relative Prominence — Ratio check against panel median for uncalibrated scans

    Args:
        declarations: Output from declaration_classifier.classify_declarations()
        ocr_results: Raw OCR results for additional context
        default_font_min_mm: Default minimum font height if not specified in rules
        calibration_result: Physical reference scale recovery result
        relative_prominence_threshold: Minimum intra-panel font height ratio (default 0.45)
        commodity_category: Unused since the Rule 5 pack-size check was removed (Rule 5 omitted
            w.e.f. 01.10.2022); kept for caller compatibility.
        pdp_area_cm2: Officer-supplied area of the Principal Display Panel. Selects the Rule 7(2)
            Table-I minimum; when absent, measured fonts are flagged for review instead of judged.

    Returns:
        List of DeclarationField results, one per rule.
    """
    config = load_rules()
    rules = config.get("rules", [])
    # ── Placement Validation (Rule 8(1) PDP co-location) ──
    # Build a map of field -> bbox center for detected fields
    bbox_centers = {}
    for rule in rules:
        field_name = rule["field"]
        detection = declarations.get(field_name, {})
        if detection.get("detected"):
            ocr_entries = detection.get("ocr_entries", [])
            if ocr_entries:
                # Calculate average center of all bounding boxes for this field
                xs, ys = [], []
                for entry in ocr_entries:
                    if hasattr(entry, 'bbox') and entry.bbox:
                        cx = (entry.bbox.top_left[0] + entry.bbox.top_right[0] +
                              entry.bbox.bottom_right[0] + entry.bbox.bottom_left[0]) / 4
                        cy = (entry.bbox.top_left[1] + entry.bbox.top_right[1] +
                              entry.bbox.bottom_right[1] + entry.bbox.bottom_left[1]) / 4
                        xs.append(cx)
                        ys.append(cy)
                if xs and ys:
                    bbox_centers[field_name] = [sum(xs) / len(xs), sum(ys) / len(ys)]

    # Determine image dimensions from OCR bounding boxes (approximate)
    all_x, all_y = [], []
    for entry in ocr_results:
        if hasattr(entry, 'bbox') and entry.bbox:
            for pt in [entry.bbox.top_left, entry.bbox.top_right,
                       entry.bbox.bottom_right, entry.bbox.bottom_left]:
                all_x.append(pt[0])
                all_y.append(pt[1])

    img_width = max(all_x) if all_x else 1.0
    img_height = max(all_y) if all_y else 1.0

    # Geometry confidence check
    geometry_confidence = calculate_geometry_confidence(ocr_results, bbox_centers)
    GEOMETRY_CONFIDENCE_THRESHOLD = 0.65
    unclear_geometry = geometry_confidence < GEOMETRY_CONFIDENCE_THRESHOLD

    # Placement Rule 1: MRP and Net Quantity must be on the Principal Display Panel (PDP), Rule 8(1)
    # We check if they are within the same spatial quadrant or within a reasonable proximity
    PDP_PROXIMITY_THRESHOLD = 0.4  # max 40% of image dimension apart
    pdp_fields = ["mrp", "net_quantity"]
    pdp_centers = {f: bbox_centers[f] for f in pdp_fields if f in bbox_centers}

    placement_issues = {}  # field_name -> list of placement violations

    if len(pdp_centers) == 2:
        dx = abs(pdp_centers["mrp"][0] - pdp_centers["net_quantity"][0]) / max(img_width, 1)
        dy = abs(pdp_centers["mrp"][1] - pdp_centers["net_quantity"][1]) / max(img_height, 1)
        distance = (dx ** 2 + dy ** 2) ** 0.5

        if distance > PDP_PROXIMITY_THRESHOLD:
            violation_msg = (
                f"PLACEMENT: MRP and Net Quantity are separated by {distance:.0%} of "
                f"the label area. Rule 8(1) requires every declaration to appear "
                f"on the Principal Display Panel (PDP)."
            )
            placement_issues.setdefault("mrp", []).append(violation_msg)
            placement_issues.setdefault("net_quantity", []).append(violation_msg)

    # Placement Rule 2: Key declarations should not be in extreme margins
    # (bottom 5% or right-edge 5% often indicates hidden/obscured text)
    MARGIN_THRESHOLD = 0.05
    for field_name, center in bbox_centers.items():
        norm_x = center[0] / max(img_width, 1)
        norm_y = center[1] / max(img_height, 1)

        if norm_y > (1.0 - MARGIN_THRESHOLD) or norm_x > (1.0 - MARGIN_THRESHOLD):
            if field_name in ["mrp", "net_quantity", "manufacturer_details"]:
                placement_issues.setdefault(field_name, []).append(
                    f"PLACEMENT: '{field_name}' appears in the extreme margin of the "
                    f"label (position: {norm_x:.0%}, {norm_y:.0%}). Rule 9(1)(a) requires "
                    f"declarations to be legible and prominent, not hidden."
                )

    # Placement Rule 3: Critical declarations scattered across distant regions
    # If more than 2 key fields have centers spread > 60% of image diagonal, flag
    key_fields = ["mrp", "net_quantity", "manufacturer_details", "consumer_care"]
    key_centers = [bbox_centers[f] for f in key_fields if f in bbox_centers]

    if len(key_centers) >= 3:
        from itertools import combinations
        max_spread = 0
        for c1, c2 in combinations(key_centers, 2):
            dx = abs(c1[0] - c2[0]) / max(img_width, 1)
            dy = abs(c1[1] - c2[1]) / max(img_height, 1)
            spread = (dx ** 2 + dy ** 2) ** 0.5
            max_spread = max(max_spread, spread)

        if max_spread > 0.7:
            for f in key_fields:
                if f in bbox_centers:
                    placement_issues.setdefault(f, []).append(
                        f"PLACEMENT: Mandatory declarations are excessively scattered "
                        f"across the label (max spread: {max_spread:.0%} of diagonal). "
                        f"Rule 8(1) requires every declaration to appear on the Principal Display Panel."
                    )

    # ── Relative Prominence Baseline (Section 5) ──
    # Calculate intra-panel median font height in pixels for uncalibrated scans
    valid_px_heights = [
        r.font_height_px for r in ocr_results
        if hasattr(r, "font_height_px") and r.font_height_px and r.font_height_px > 0
    ]
    median_panel_font_px = float(np.median(valid_px_heights)) if valid_px_heights else None

    # Build final results list
    results: List[DeclarationField] = []
    num_ocr_boxes = len(ocr_results)
    low_coverage = num_ocr_boxes < 4
    imported = is_imported_package(ocr_results)

    for rule in rules:
        field_name = rule["field"]
        display_name = rule["display_name"]
        required = rule.get("required", True)
        note = None
        if required and rule.get("required_when") == "imported" and not imported:
            required = False
            note = NOT_IMPORTED_NOTE

        detection = declarations.get(field_name, {})
        detected = detection.get("detected", False)
        value = detection.get("value")
        confidence = detection.get("confidence")
        ocr_entries = detection.get("ocr_entries", [])

        violations: List[str] = []
        compliant = True

        # ── Absence Classification (Section 6) ──
        if detected:
            detection_status = DetectionStatus.DETECTED
            coverage_review_req = False
            coverage_review_msg = None
        else:
            if low_coverage:
                detection_status = DetectionStatus.NOT_DETECTED_LOW_COVERAGE
                coverage_review_req = True
                coverage_review_msg = (
                    f"Label spatial coverage is low (only {num_ocr_boxes} text regions detected). "
                    f"Absence of mandatory declaration '{display_name}' cannot be verified without physical inspection."
                )
            else:
                detection_status = DetectionStatus.NOT_DETECTED_CONFIRMED_ABSENT
                coverage_review_req = False
                coverage_review_msg = None

        # ── Check 1: Presence ──
        if required and not detected:
            if detection_status == DetectionStatus.NOT_DETECTED_LOW_COVERAGE:
                # Per prompt: when coverage is too low to assert absence, flag coverage_review_required
                # instead of issuing an unverified missing declaration citation.
                compliant = True
            else:
                violations.append(
                    f"MISSING: '{display_name}' is a mandatory declaration "
                    f"under {rule.get('section_reference', 'LMPC Rules 2011')} "
                    f"but was not detected on the label."
                )
                compliant = False

        # ── Check 2: Format (only if detected) ──
        if detected and value and rule.get("format_regex"):
            format_pattern = re.compile(rule["format_regex"], re.IGNORECASE)
            if not format_pattern.search(value):
                violations.append(
                    f"FORMAT: Detected value '{value}' does not match the "
                    f"expected format for {display_name}."
                )
                compliant = False

        # ── Check 3: Font Size & Uncertainty (Section 4 & 5) ──
        # Rule 7(2) applies to "any numeral and letter in the declaration required under these rules".
        font_applies = rule.get("font_size_applies", False)
        required_font_mm = None
        if font_applies:
            if default_font_min_mm != 1.0:
                required_font_mm = default_font_min_mm
            else:
                # None when the officer did not supply the PDP area → font review, never a violation
                required_font_mm = required_font_height_for_area(pdp_area_cm2)

        font_height_mm = None
        font_uncertainty_mm = None
        lower_bound_mm = None
        upper_bound_mm = None
        font_review_req = False
        font_review_msg = None
        rel_prominence_flag = False
        rel_prominence_note = None
        price_review_req = False
        price_review_msg = None

        cal_method = calibration_result.calibration_method if calibration_result else None
        cal_conf = calibration_result.calibration_confidence if calibration_result else None
        is_calibrated = (
            calibration_result is not None
            and calibration_result.pixels_per_mm is not None
            and calibration_result.pixels_per_mm > 0
        )
        is_explicitly_uncalibrated = (
            calibration_result is not None
            and calibration_result.pixels_per_mm is None
        )

        # Get maximum pixel height for this field
        field_font_px = None
        if detected and ocr_entries:
            pxs = [e.font_height_px for e in ocr_entries if hasattr(e, "font_height_px") and e.font_height_px]
            field_font_px = max(pxs) if pxs else None

        if detected and font_applies:
            if is_calibrated:
                ppm = calibration_result.pixels_per_mm
                if field_font_px is not None:
                    raw_font_mm = field_font_px / ppm
                else:
                    raw_font_mm = detection.get("max_font_height_mm")

                if raw_font_mm is not None:
                    unc_mm, lower_mm, upper_mm = calculate_font_uncertainty(
                        raw_font_mm, cal_method, geometry_confidence
                    )
                    font_height_mm = round(raw_font_mm, 2)
                    font_uncertainty_mm = unc_mm
                    lower_bound_mm = lower_mm
                    upper_bound_mm = upper_mm

                    if required_font_mm is None:
                        font_review_req = True
                        font_review_msg = (
                            f"Measured font height {font_height_mm:.2f}mm, but the PDP area was not supplied, "
                            f"so the Rule 7(2) minimum cannot be determined. Flagged for manual officer verification."
                        )
                    elif lower_bound_mm >= required_font_mm:
                        font_review_req = False
                    elif upper_bound_mm < required_font_mm:
                        violations.append(
                            f"FONT SIZE: Measured font height {font_height_mm:.2f}mm "
                            f"[{lower_bound_mm:.2f}mm - {upper_bound_mm:.2f}mm] "
                            f"is below minimum required {required_font_mm:.1f}mm "
                            f"per LMPC Rule 7(2)."
                        )
                        compliant = False
                    else:
                        font_review_req = True
                        font_review_msg = (
                            f"Measurement uncertainty interval [{lower_bound_mm:.2f}mm - {upper_bound_mm:.2f}mm] "
                            f"straddles Rule 7(2) minimum of {required_font_mm:.1f}mm. "
                            f"Flagged for manual officer verification."
                        )
            elif is_explicitly_uncalibrated:
                # Uncalibrated quick scan mode: never guess a DPI!
                font_height_mm = None
                font_review_req = True
                font_review_msg = (
                    "Uncalibrated scan (no physical reference detected in frame). "
                    "Physical font height cannot be legally certified in millimeters without calibration reference."
                )
                if median_panel_font_px and field_font_px:
                    ratio = field_font_px / median_panel_font_px
                    if ratio < relative_prominence_threshold:
                        rel_prominence_flag = True
                        rel_prominence_note = (
                            f"Relative prominence warning: Declaration font height ({field_font_px:.1f}px) "
                            f"is {ratio:.0%} of panel median ({median_panel_font_px:.1f}px), "
                            f"below prominence threshold ({relative_prominence_threshold:.0%})."
                        )
            else:
                # calibration_result was None (legacy caller or unit tests with pre-populated mm)
                raw_font_mm = detection.get("max_font_height_mm")
                if raw_font_mm is not None:
                    unc_mm, lower_mm, upper_mm = calculate_font_uncertainty(
                        raw_font_mm, "none", geometry_confidence
                    )
                    font_height_mm = round(raw_font_mm, 2)
                    font_uncertainty_mm = unc_mm
                    lower_bound_mm = lower_mm
                    upper_bound_mm = upper_mm

                    if required_font_mm is None:
                        font_review_req = True
                        font_review_msg = (
                            "PDP area not supplied, so the Rule 7(2) minimum cannot be determined."
                        )
                    elif upper_bound_mm < required_font_mm:
                        violations.append(
                            f"FONT SIZE: Measured font height ({font_height_mm:.1f}mm) "
                            f"is below the minimum required ({required_font_mm}mm) "
                            f"per LMPC Rule 7(2)."
                        )
                        compliant = False
                    elif lower_bound_mm < required_font_mm <= upper_bound_mm:
                        font_review_req = True
                        font_review_msg = (
                            f"Measurement uncertainty interval [{lower_bound_mm:.2f}mm - {upper_bound_mm:.2f}mm] "
                            f"straddles Rule 7(2) minimum of {required_font_mm:.1f}mm."
                        )

        # ── Check 4: Special requirements ──
        if field_name == "mrp" and detected and value:
            # 4a. Mandatory inclusive of all taxes text (Rule 6(1)(e))
            must_include_taxes = rule.get("must_include_taxes", False)
            if must_include_taxes:
                taxes_keywords = rule.get("taxes_keywords", [])
                value_lower = value.lower()
                full_ocr_text = " ".join(r.text.lower() for r in ocr_results)
                has_taxes_text = any(
                    kw in value_lower or kw in full_ocr_text
                    for kw in taxes_keywords
                )
                # OCR reads the printed 'Incl. of all taxes' as e.g. '(Uncl , ol all laxes)'.
                taxes_ocr_pattern = rule.get("taxes_ocr_pattern")
                if not has_taxes_text and taxes_ocr_pattern:
                    has_taxes_text = bool(re.search(taxes_ocr_pattern, f"{value_lower} {full_ocr_text}", re.IGNORECASE))
                if not has_taxes_text:
                    violations.append(
                        "MRP TAXES: MRP declaration should include "
                        "'inclusive of all taxes' text as required by LMPC rules."
                    )

            # 4b. Conflicting MRPs on one package → officer review (no clean statutory citation)
            is_dup_conflict, dup_msg = validate_duplicate_mrp(ocr_results)
            if is_dup_conflict and dup_msg:
                price_review_req = True
                price_review_msg = dup_msg

            # 4c. Unit Sale Price (USP) Mathematical Reconciliation (Rule 6(11))
            usp_detection = declarations.get("unit_sale_price", {})
            usp_val = usp_detection.get("value")
            net_qty_val = declarations.get("net_quantity", {}).get("value")
            if usp_val and net_qty_val:
                is_usp_valid, usp_msg = validate_usp_reconciliation(value, net_qty_val, usp_val)
                if not is_usp_valid and usp_msg:
                    violations.append(usp_msg)
                    compliant = False

        if field_name == "net_quantity" and detected and value:
            full_ocr_text = " ".join(r.text for r in ocr_results)

            # 4d. Rule 12(6) Prohibited Qualifying Expressions ("approximate", "minimum", "not less than").
            # Only the quantity declaration's own OCR lines are checked: the same words elsewhere on the
            # label (e.g. "approximate values" in a nutrition table) are not qualifiers on the net quantity.
            quantity_lines = " ".join(e.text for e in ocr_entries if hasattr(e, "text"))
            qualifier_violations = validate_prohibited_expressions(value, quantity_lines)
            if qualifier_violations:
                violations.extend(qualifier_violations)
                compliant = False

            # 4e. Rule 13(2) & 13(5) Unit Symbols & Fraction Requirements
            unit_violations = validate_unit_formatting(value)
            if unit_violations:
                violations.extend(unit_violations)
                compliant = False

        if field_name == "manufacturer_details" and detected:
            requires_pin = rule.get("requires_pin_code", False)
            if requires_pin and value:
                pin_pattern = re.compile(r"\b\d{6}\b")
                full_ocr_text = " ".join(r.text for r in ocr_results)
                if not pin_pattern.search(value) and not pin_pattern.search(full_ocr_text):
                    violations.append(
                        "ADDRESS: Manufacturer address should include a 6-digit PIN code."
                    )

        if field_name == "consumer_care" and detected:
            requires_contact = rule.get("requires_phone_or_email", False)
            if requires_contact and value:
                has_contact = (
                    re.search(r"\d{10,}", re.sub(r"[\s\-]", "", value)) or  # landline '02562-233815'
                    re.search(r"@", value)
                )
                if not has_contact:
                    violations.append(
                        "CONTACT: Consumer care details should include "
                        "a telephone number or email address."
                    )

        # ── Check 5: Placement ──
        field_placement_violations = placement_issues.get(field_name, [])
        placement_ok = len(field_placement_violations) == 0
        placement_review_req = False
        placement_review_msg = None

        if not placement_ok:
            if unclear_geometry:
                # Geometric ambiguity (e.g. curved bottle surface, angled photo, or sparse spatial anchors):
                # Do NOT trigger a hard statutory violation or seizure notice.
                # Flag for manual officer review instead.
                placement_review_req = True
                placement_review_msg = (
                    f"Label surface curvature or sparse spatial geometry (confidence {geometry_confidence:.0%}) "
                    f"precludes certified automated PDP verification. Rule 8(1) placement flagged for manual officer verification."
                )
                placement_ok = True  # Do not trigger a false fail
                field_placement_violations = []  # Clear from hard statutory violations
            else:
                compliant = False
                violations.extend(field_placement_violations)

        results.append(
            DeclarationField(
                field_name=field_name,
                display_name=display_name,
                detected=detected,
                detection_status=detection_status,
                coverage_review_required=coverage_review_req,
                coverage_review_reason=coverage_review_msg,
                value=value,
                compliant=compliant,
                violations=violations,
                font_height_mm=font_height_mm,
                font_uncertainty_mm=font_uncertainty_mm,
                lower_bound_mm=lower_bound_mm,
                upper_bound_mm=upper_bound_mm,
                font_review_required=font_review_req,
                font_review_reason=font_review_msg,
                calibration_method=cal_method,
                calibration_confidence=cal_conf,
                relative_prominence_flag=rel_prominence_flag,
                relative_prominence_note=rel_prominence_note,
                required_font_height_mm=required_font_mm,
                confidence=confidence,
                placement_compliant=placement_ok,
                placement_violations=field_placement_violations,
                bbox_center=bbox_centers.get(field_name),
                placement_review_required=placement_review_req,
                placement_review_reason=placement_review_msg,
                price_review_required=price_review_req,
                price_review_reason=price_review_msg,
                pdp_area_cm2=pdp_area_cm2,
                note=note if not detected else None,
            )
        )

    logger.info(
        f"Compliance check complete: "
        f"{sum(1 for r in results if r.compliant)}/{len(results)} fields compliant"
    )

    return results


def generate_summary(declarations: List[DeclarationField]) -> str:
    """
    Generate a human-readable compliance summary.

    Args:
        declarations: List of validated declaration results.

    Returns:
        Summary string.
    """
    total = len(declarations)
    compliant_count = sum(1 for d in declarations if d.compliant)
    non_compliant = [d for d in declarations if not d.compliant]

    review_sections = []

    # 1. Placement reviews
    placement_fields = [d for d in declarations if getattr(d, "placement_review_required", False)]
    if placement_fields:
        r_names = ", ".join(d.display_name for d in placement_fields)
        review_sections.append(
            f"🔍 PLACEMENT REVIEW: Surface curvature/geometry confidence was below threshold. "
            f"Officer must visually confirm Rule 8(1) PDP placement for {r_names}."
        )

    # 2. Font measurement reviews
    font_fields = [d for d in declarations if getattr(d, "font_review_required", False)]
    if font_fields:
        f_names = ", ".join(d.display_name for d in font_fields)
        review_sections.append(
            f"🔍 FONT VERIFICATION REQUIRED: Uncertainty interval straddles Rule 7(2) minimum, uncalibrated scan, or PDP area not supplied. "
            f"Physical ruler/caliper confirmation recommended for {f_names}."
        )

    # 3. Coverage reviews
    cov_fields = [d for d in declarations if getattr(d, "coverage_review_required", False)]
    if cov_fields:
        c_names = ", ".join(d.display_name for d in cov_fields)
        review_sections.append(
            f"🔍 LOW COVERAGE: Few text regions detected on panel. "
            f"Absence of {c_names} requires physical package inspection."
        )

    # 4. Conflicting MRP reviews
    price_fields = [d for d in declarations if getattr(d, "price_review_required", False)]
    for d in price_fields:
        review_sections.append(f"🔍 MRP REVIEW: {d.price_review_reason}")

    # 5. Relative prominence warnings
    prom_fields = [d for d in declarations if getattr(d, "relative_prominence_flag", False)]
    if prom_fields:
        p_names = ", ".join(d.display_name for d in prom_fields)
        review_sections.append(
            f"⚠️ RELATIVE PROMINENCE: {p_names} text height is significantly smaller than panel median."
        )

    review_note = ""
    if review_sections:
        review_note = "\n\n" + "\n\n".join(review_sections)

    if compliant_count == total:
        return (
            f"✅ COMPLIANT: All {total} mandatory declarations under "
            f"LMPC Rules 2011 are present and meet requirements."
            f"{review_note}"
        )

    summary_parts = [
        f"⚠️ NON-COMPLIANT: {len(non_compliant)} of {total} mandatory "
        f"declarations have issues.",
        "",
        "Violations found:",
    ]

    for decl in non_compliant:
        summary_parts.append(f"  • {decl.display_name}:")
        for violation in decl.violations:
            summary_parts.append(f"    - {violation}")

    if review_note:
        summary_parts.append(review_note)

    return "\n".join(summary_parts)
