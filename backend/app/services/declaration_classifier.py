"""
LenseScan Declaration Classifier.
Regex/NLP-based detection of LMPC mandatory fields from OCR text.
Maps raw OCR results to structured label declarations.
"""

import re
import logging
from typing import Dict, List, Optional, Tuple

from app.schemas.scan import OCRResult

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────
# Regex patterns for each LMPC mandatory declaration field.
# Each entry: (field_name, list_of_compiled_patterns)
# ──────────────────────────────────────────────────────────

FIELD_PATTERNS: Dict[str, List[re.Pattern]] = {
    "mrp": [
        re.compile(
            r"(?:M\.?\s*R\.?\s*P\.?|Maximum\s*Retail\s*Price|Retail\s*Price)"
            r"\s*[:\-?]?\s*(?:[₹\?]|Rs\.?|INR)?\s*[:\-]?\s*[\d,]+(?:\.\d{1,2})?(?:\s*(?:incl\.?|inclusive|all\s*taxes|\([^)]*taxes[^)]*\)))?",
            re.IGNORECASE,
        ),
        re.compile(r"[₹]\s*[\d,]+(?:\.\d{1,2})?", re.IGNORECASE),
        re.compile(
            r"(?:Rs\.?|INR)\s*[\d,]+(?:\.\d{1,2})?.{0,40}?(?:incl|inclusive|all\s*taxes)",
            re.IGNORECASE,
        ),
    ],
    "net_quantity": [
        re.compile(
            r"(?:N[eiaozct]{1,2}t?\.?\s*(?:Wt\.?|Weight|Qty\.?|Quantity|Content|Vol\.?|Volume))"
            r"\s*[:\-]?\s*[\d.]+\s*(?:g|gm|gms|kg|kgs|ml|mL|l|L|ltr|litre|cm|m|mm|pieces?|pcs?|nos?)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b[\d.]+\s*(?:g|gm|kg|ml|mL|l|L|ltr)\b",
            re.IGNORECASE,
        ),
    ],
    "manufacturing_date": [
        re.compile(
            r"(?:Mf[gd]\.?|Manu?f(?:actur(?:ed|ing))?|Pack(?:ed|ing)?|PKD\.?|Dom|Date\s*of\s*(?:Manufacture|Mfg|Packing))"
            r"\s*(?:Date|On|Dt\.?)?\s*[:\-]?\s*"
            r"(?:\d{1,2}[\s/\-\.]*[A-Za-z]{3,9}[\s/\-\.,]*\d{2,4}|\d{1,2}[\s/\-\.]\d{1,2}[\s/\-\.]\d{2,4}|\w+[\s/\-\.]\d{2,4}|\d{2,4})",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:Date\s*of\s*(?:Manufacture|Mfg|Packing))\s*[:\-]?\s*"
            r"(?:\d{1,2}[\s/\-\.]*[A-Za-z]{3,9}[\s/\-\.,]*\d{2,4}|\d{1,2}[\s/\-\.]\d{1,2}[\s/\-\.]\d{2,4}|\w+[\s/\-\.]\d{2,4})",
            re.IGNORECASE,
        ),
    ],
    "best_before": [
        re.compile(
            r"(?:Best\s*Before|Exp(?:iry)?\.?\s*(?:Date)?|Use\s*By|BB|"
            r"Best\s*By|Shelf\s*Life)"
            r"\s*[:\-]?\s*"
            r"(?:\d{1,2}[\s/\-\.]\d{1,2}[\s/\-\.]\d{2,4}|\d+\s*(?:months?|days?|years?))",
            re.IGNORECASE,
        ),
    ],
    "manufacturer_details": [
        re.compile(
            r"(?:REGD[^\w]*OFF[A-Z]*|Manu?f(?:actur(?:ed|ing)|d\.?)?|Packed|Marketed|Distributed|Imported)"
            r"(?:\s*(?:by|&\s*Packed\s*by))?[\s:;\-\.]*(?:[A-Z]{1,2}[:;\-\.\s]+)?([A-Za-z0-9\s,\.\-&]{4,60})",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b([A-Za-z0-9\s,\.\-&]{3,40}(?:Pvt\.?\s*Ltd\.?|Private\s*Limited|\bLtd\.?|\bInc\.?|\bCorp\.?|Industries|Enterprises))\b",
            re.IGNORECASE,
        ),
    ],
    "consumer_care": [
        # OCR often reads 'CONSUMER' as 'CONSVMER' and cuts 'CUSTOMER' to 'STOMER' on crimped pouches;
        # a 'CARE NO:' followed by a number is the same declaration.
        re.compile(
            r"(?:[CLO][o0]ns[uv]mer|Cus?tomer|\bstomer)\s*(?:Care|Service|Helpline|Grievance|Support|"
            r"Executive|Cell|Complaint|Contact)"
            r"|\bCare\s*(?:No|Number)\b\.?\s*[:\-]?\s*\+?\d",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:Toll\s*Free|Helpline|Freephone)\s*[:\-]?\s*[\d\-\s+()]+",
            re.IGNORECASE,
        ),
        re.compile(
            r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
            re.IGNORECASE,
        ),
    ],
    "country_of_origin": [
        re.compile(
            r"(?:Made\s*in|Product\s*of|Country\s*of\s*Origin|Assembled\s*in|"
            r"Origin)\s*[:\-]?\s*(?:India|Bharat|[A-Z][a-z]+)",
            re.IGNORECASE,
        ),
    ],
    "generic_name": [
        # Generic name heuristic: descriptors or common FMCG commodity names
        re.compile(
            r"(?:contains?|ingredients?|description|commodity|product\s*name)\s*[:\-]?",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:Gathiya|Wafers|Chakali|Sauce|Flour|Maida|Soup|Noodles|Biscuits|Talc|Powder|Namkeen|Snacks)\b",
            re.IGNORECASE,
        ),
    ],
    "unit_sale_price": [
        re.compile(
            r"(?:U\.?\s*S\.?\s*P\.?|Unit\s*Sale\s*Price)\s*[:\-?]?\s*(?:[₹\?]|Rs\.?|INR)?\s*[\d,]+(?:\.\d{1,2})?\s*(?:/|per)\s*(?:[\d.]*\s*(?:g|gm|kg|ml|mL|l|L|nos?|pcs?|piece))\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:[₹]|Rs\.?)\s*[\d,]+(?:\.\d{1,2})?\s*(?:/|per)\s*(?:[\d.]*\s*(?:g|gm|kg|ml|mL|l|L|nos?|pcs?))\b",
            re.IGNORECASE,
        ),
    ],
}

# Additional patterns for extracting specific values
ADDRESS_PIN_PATTERN = re.compile(r"\b\d{6}\b")  # Indian PIN code
PHONE_PATTERN = re.compile(
    r"(?:\+91[\-\s]?)?(?:[6-9]\d{9}|1800[\-\s]?\d{3,4}[\-\s]?\d{3,4}|\d{10,11}|0\d{2,4}[\-\s]\d{6,8})"
)
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# Letter O read in place of the digit 0 inside a quantity ('10Og' printed as 100g).
_O_AS_ZERO = re.compile(r"(?<=\d)[Oo](?=\d|\s?(?:g|kg|mg|ml|mL|l|L)\b)")

# Dates are often in their own OCR box beside the label ('Pkd Date' | '31 MAR 26'). Those two
# fields are matched box by box and, failing that, by pairing a label box with a neighbouring
# date box. They are never matched on the joined text of the whole photo, which can glue a
# label to a date printed somewhere else on the pack.
_MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*"
DATE_VALUE = re.compile(
    rf"\b(?:\d{{1,2}}[\s/\-.]*{_MONTH}[\s/\-.,]*\d{{2,4}}|{_MONTH}[\s/\-.]*\d{{2,4}}|\d{{1,2}}[/\-.]\d{{2,4}}(?:[/\-.]\d{{2,4}})?)\b",
    re.IGNORECASE,
)
DATE_LABELS = {
    "manufacturing_date": re.compile(
        r"\b(?:pkd|pkg|mfd|mfg|packed\s*on|packing\s*date|manufactured\s*on|"
        r"date\s*of\s*(?:packing|manufacture|mfg|mfd|pkg))\b",
        re.IGNORECASE,
    ),
    "best_before": re.compile(r"\b(?:best\s*before|use\s*by|expiry|exp\.?\s*date)\b", re.IGNORECASE),
}


def _box_extent(r: OCRResult) -> Tuple[float, float, float, float]:
    b = r.bbox
    xs = [b.top_left[0], b.top_right[0], b.bottom_right[0], b.bottom_left[0]]
    ys = [b.top_left[1], b.top_right[1], b.bottom_right[1], b.bottom_left[1]]
    return min(xs), max(xs), min(ys), max(ys)


def _pair_label_with_date(field_name: str, ocr_results: List[OCRResult]) -> Optional[Tuple[OCRResult, OCRResult]]:
    """
    Find a label box ('Pkd Date', 'use By:') and the date box right next to it: on the same line
    (vertical overlap, starting at most 6 label-heights to the right) or directly below/above
    (within 1.5 label-heights, overlapping horizontally). The closest candidate wins.
    """
    label_pattern = DATE_LABELS[field_name]
    best, best_dist = None, float("inf")
    for label in ocr_results:
        if not label_pattern.search(label.text) or DATE_VALUE.search(label.text):
            continue
        lx0, lx1, ly0, ly1 = _box_extent(label)
        lh = max(ly1 - ly0, 1.0)
        for date in ocr_results:
            if date is label or not DATE_VALUE.search(date.text):
                continue
            dx0, dx1, dy0, dy1 = _box_extent(date)
            dh = max(dy1 - dy0, 1.0)
            v_overlap = min(ly1, dy1) - max(ly0, dy0)
            h_overlap = min(lx1, dx1) - max(lx0, dx0)
            same_line = v_overlap >= 0.3 * min(lh, dh) and -0.5 * lh <= dx0 - lx1 <= 6 * lh
            stacked = h_overlap > 0 and (0 <= dy0 - ly1 <= 1.5 * lh or 0 <= ly0 - dy1 <= 1.5 * lh)
            if not (same_line or stacked):
                continue
            dist = abs((dx0 + dx1) / 2 - (lx0 + lx1) / 2) + abs((dy0 + dy1) / 2 - (ly0 + ly1) / 2)
            if dist < best_dist:
                best, best_dist = (label, date), dist
    return best


def classify_declarations(
    ocr_results: List[OCRResult],
) -> Dict[str, Dict]:
    """
    Classify OCR results into LMPC mandatory declaration fields.

    Uses hierarchical matching:
    1. Specific primary patterns (e.g. 'Net Weight: 24g', 'MRP Rs 5.00') take precedence
       over generic single-token patterns.
    2. Multi-line full-text search detects declarations split across adjacent OCR boxes.
    3. Secondary fallbacks only activate if primary patterns find no matches.

    Args:
        ocr_results: List of OCR text detection results.

    Returns:
        Dictionary mapping field names to detection results.
    """
    ocr_results = [
        r.model_copy(update={"text": _O_AS_ZERO.sub("0", r.text)}) if _O_AS_ZERO.search(r.text) else r
        for r in ocr_results
    ]
    full_text = " ".join(r.text for r in ocr_results)
    declarations: Dict[str, Dict] = {}

    for field_name, patterns in FIELD_PATTERNS.items():
        matched_entries: List[OCRResult] = []
        matched_values: List[str] = []
        boxes_only = field_name in DATE_LABELS

        # 1. Primary priority: check primary pattern on full_text and individual boxes
        primary_pattern = patterns[0]
        full_match = None if boxes_only else primary_pattern.search(full_text)
        if full_match:
            matched_values.append(full_match.group(0).strip())
            _find_closest_entry(full_match.group(0), ocr_results, matched_entries)
        else:
            for ocr_result in ocr_results:
                m = primary_pattern.search(ocr_result.text)
                if m:
                    matched_entries.append(ocr_result)
                    matched_values.append(m.group(0).strip())

        # 2. Secondary fallback: only if primary pattern matched nothing
        if not matched_values and len(patterns) > 1:
            for pattern in patterns[1:]:
                full_m = None if boxes_only else pattern.search(full_text)
                if full_m:
                    matched_values.append(full_m.group(0).strip())
                    _find_closest_entry(full_m.group(0), ocr_results, matched_entries)
                    break
                for ocr_result in ocr_results:
                    m = pattern.search(ocr_result.text)
                    if m:
                        matched_entries.append(ocr_result)
                        matched_values.append(m.group(0).strip())
                        break
                if matched_values:
                    break

        # 3. Date fields: a label box paired with the date box beside it
        if not matched_values and boxes_only:
            pair = _pair_label_with_date(field_name, ocr_results)
            if pair:
                matched_entries.extend(pair)
                matched_values.append(f"{pair[0].text.strip()} {pair[1].text.strip()}")

        detected = len(matched_values) > 0
        max_font_height_mm = None
        avg_confidence = None

        if matched_entries:
            heights = [
                e.font_height_mm for e in matched_entries
                if e.font_height_mm is not None
            ]
            max_font_height_mm = max(heights) if heights else None

            confidences = [e.confidence for e in matched_entries]
            avg_confidence = sum(confidences) / len(confidences) if confidences else None

        declarations[field_name] = {
            "detected": detected,
            "value": " | ".join(matched_values) if matched_values else None,
            "ocr_entries": matched_entries,
            "max_font_height_mm": max_font_height_mm,
            "confidence": round(avg_confidence, 4) if avg_confidence else None,
        }

    # Special handling: if manufacturer_details detected, check for address components
    _enrich_manufacturer_details(declarations, ocr_results, full_text)

    # Special handling: if consumer_care detected, extract phone/email
    _enrich_consumer_care(declarations, full_text)

    logger.info(
        f"Classified declarations: "
        f"{sum(1 for d in declarations.values() if d['detected'])}/{len(declarations)} detected"
    )

    return declarations


def _find_closest_entry(
    match_text: str,
    ocr_results: List[OCRResult],
    matched_entries: List[OCRResult],
):
    """Find the OCR entry whose text best matches the given match text."""
    best_score = 0
    best_entry = None
    match_lower = match_text.lower()

    for entry in ocr_results:
        if entry in matched_entries:
            continue
        entry_lower = entry.text.lower()
        # Simple overlap score
        if match_lower in entry_lower or entry_lower in match_lower:
            score = len(entry.text)
            if score > best_score:
                best_score = score
                best_entry = entry

    if best_entry:
        matched_entries.append(best_entry)


def _enrich_manufacturer_details(
    declarations: Dict[str, Dict],
    ocr_results: List[OCRResult],
    full_text: str,
):
    """Check for address components (PIN code) in manufacturer details."""
    mfg = declarations.get("manufacturer_details", {})
    if mfg.get("detected"):
        pin_match = ADDRESS_PIN_PATTERN.search(full_text)
        if pin_match:
            current_value = mfg.get("value", "")
            if pin_match.group(0) not in (current_value or ""):
                mfg["value"] = f"{current_value} [PIN: {pin_match.group(0)}]"


def _enrich_consumer_care(
    declarations: Dict[str, Dict],
    full_text: str,
):
    """Extract specific phone numbers and email addresses for consumer care."""
    care = declarations.get("consumer_care", {})
    if care.get("detected"):
        phones = PHONE_PATTERN.findall(full_text)
        emails = EMAIL_PATTERN.findall(full_text)
        enriched_parts = []
        if phones:
            enriched_parts.append(f"Phone: {', '.join(phones[:3])}")
        if emails:
            enriched_parts.append(f"Email: {', '.join(emails[:3])}")
        if enriched_parts:
            current_value = care.get("value", "")
            care["value"] = f"{current_value} [{'; '.join(enriched_parts)}]"
