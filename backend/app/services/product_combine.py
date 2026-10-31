"""
Combine several photos of one product into a single set of declaration results.

Officers photograph a panel twice: once clean (all text readable) and once with the
40 mm ArUco marker (for millimetre scale; the marker may cover some text). Each photo is
checked on its own by the rule engine, then this module merges the results:

- Text (the declaration's value, presence and every non-font check) comes from a photo
  WITHOUT the marker, where nothing is covered. A marker photo supplies text only when no
  clean photo shows that declaration.
- Font size comes only from a photo WITH the marker. If no marker photo shows the
  declaration, its font size goes to officer review — no scale is borrowed or guessed.
- A declaration is "missing" only if no photo shows it. A confirmed absence in any photo
  outweighs low-coverage photos; if every photo had low coverage, it stays a review.
"""

from dataclasses import dataclass
from typing import Dict, List

from app.schemas.scan import DeclarationField, DetectionStatus

NOT_MEASURED_REASON = (
    "Found only in photos without the marker, so its font height could not be measured. "
    "Officer must check the Rule 7(2) minimum by hand."
)


@dataclass
class PhotoResult:
    label: str  # file name shown on the report
    calibrated: bool  # True when the ArUco marker gave a millimetre scale
    fields: List[DeclarationField]


def combine_photo_results(photos: List[PhotoResult]) -> List[DeclarationField]:
    """Merge per-photo declaration results into one result per declaration."""
    order: List[str] = []
    by_field: Dict[str, List[tuple]] = {}
    for photo in photos:
        for field in photo.fields:
            if field.field_name not in by_field:
                by_field[field.field_name] = []
                order.append(field.field_name)
            by_field[field.field_name].append((photo, field))

    return [_combine_one(by_field[name]) for name in order]


_FONT_FIELDS = (
    "font_height_mm",
    "font_uncertainty_mm",
    "lower_bound_mm",
    "upper_bound_mm",
    "required_font_height_mm",
    "font_review_required",
    "font_review_reason",
    "calibration_method",
    "calibration_confidence",
)


def _best(pairs):
    return max(pairs, key=lambda pf: pf[1].confidence or 0.0)[1]


def _combine_one(observations: List[tuple]) -> DeclarationField:
    detected = [(p, f) for p, f in observations if f.detected]

    if detected:
        clean = [(p, f) for p, f in detected if not p.calibrated]
        marked = [(p, f) for p, f in detected if p.calibrated and f.font_height_mm is not None]

        # Text, presence and every non-font check come from a photo WITHOUT the marker
        # (nothing covered); a marker photo supplies text only if no clean photo shows it.
        text_src = _best(clean) if clean else _best(detected)
        result = text_src.model_copy(deep=True)
        result.violations = [v for v in result.violations if not v.startswith("FONT SIZE")]

        # Font size comes only from a photo WITH the marker.
        font_src = _best(marked) if marked else None
        if font_src is not None:
            for name in _FONT_FIELDS:
                setattr(result, name, getattr(font_src, name))
            font_violations = [v for v in font_src.violations if v.startswith("FONT SIZE")]
            result.violations.extend(font_violations)
            # Non-font compliance follows the text photo; a measured font violation makes it non-compliant.
            text_ok = text_src.compliant or (not clean and not _has_non_font_failure(text_src))
            result.compliant = text_ok and not font_violations
        else:
            result.font_height_mm = None
            result.font_uncertainty_mm = None
            result.lower_bound_mm = None
            result.upper_bound_mm = None
            result.font_review_required = True
            result.font_review_reason = NOT_MEASURED_REASON
        return result

    return _combine_absent(observations)


def _has_non_font_failure(field: DeclarationField) -> bool:
    """True when a field failed for a reason other than font size (e.g. FORMAT, Rule 12(6))."""
    return not field.compliant and any(not v.startswith("FONT SIZE") for v in field.violations)


def _combine_absent(observations: List[tuple]) -> DeclarationField:
    # Not found in any photo: a confirmed absence anywhere is a real MISSING finding. A photo that
    # made the declaration required (e.g. 'Imported by' on the back panel) outweighs one that did not.
    confirmed = [f for _, f in observations if f.detection_status == DetectionStatus.NOT_DETECTED_CONFIRMED_ABSENT]
    if confirmed:
        failing = [f for f in confirmed if not f.compliant]
        return (failing or confirmed)[0].model_copy(deep=True)
    return observations[0][1].model_copy(deep=True)
