"""
LenseScan Scan Schemas.
Pydantic models for OCR results and compliance reports.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import uuid


from enum import Enum


class DetectionStatus(str, Enum):
    """Statutory detection state distinguishing unphotographed panels from true omissions."""
    DETECTED = "detected"
    NOT_DETECTED_LOW_COVERAGE = "not_detected_low_coverage"
    NOT_DETECTED_CONFIRMED_ABSENT = "not_detected_confirmed_absent"


class BoundingBox(BaseModel):
    """Bounding box coordinates for detected text."""
    top_left: List[float] = Field(..., description="[x, y] of top-left corner")
    top_right: List[float] = Field(..., description="[x, y] of top-right corner")
    bottom_right: List[float] = Field(..., description="[x, y] of bottom-right corner")
    bottom_left: List[float] = Field(..., description="[x, y] of bottom-left corner")


class OCRResult(BaseModel):
    """Single OCR text detection result."""
    text: str
    bbox: BoundingBox
    confidence: float = Field(..., ge=0.0, le=1.0)
    font_height_px: float = Field(..., description="Text height in pixels")
    font_height_mm: Optional[float] = Field(
        None, description="Physical text height in mm (requires calibration)"
    )


class DeclarationField(BaseModel):
    """Result of validating a single LMPC mandatory declaration."""
    field_name: str = Field(..., description="Machine identifier (e.g., 'mrp')")
    display_name: str = Field(
        ..., description="Human-readable name (e.g., 'Maximum Retail Price')"
    )
    detected: bool = Field(..., description="Was this field found on the label?")
    detection_status: DetectionStatus = Field(
        default=DetectionStatus.DETECTED,
        description="Absence classification: detected, low coverage, or confirmed absent",
    )
    coverage_review_required: bool = Field(
        False, description="Flagged for manual review if low OCR coverage precludes confirming absence"
    )
    coverage_review_reason: Optional[str] = Field(
        None, description="Reason why absence cannot be confirmed without manual verification"
    )
    value: Optional[str] = Field(
        None, description="Extracted value if detected"
    )
    compliant: bool = Field(
        ..., description="Does this field pass all LMPC rules?"
    )
    violations: List[str] = Field(
        default_factory=list,
        description="List of specific rule violations",
    )
    # Physical Font Measurement & Uncertainty (Section 4)
    font_height_mm: Optional[float] = Field(
        None, description="Measured font height in mm (None if uncalibrated)"
    )
    font_uncertainty_mm: Optional[float] = Field(
        None, description="Physical font measurement uncertainty (+- mm)"
    )
    lower_bound_mm: Optional[float] = Field(
        None, description="Lower bound of measurement interval in mm"
    )
    upper_bound_mm: Optional[float] = Field(
        None, description="Upper bound of measurement interval in mm"
    )
    font_review_required: bool = Field(
        False, description="Flagged for manual review if interval overlaps threshold or uncalibrated"
    )
    font_review_reason: Optional[str] = Field(
        None, description="Reason why font measurement requires manual review"
    )
    calibration_method: Optional[str] = Field(
        None, description="Physical calibration method (e.g. aruco_40mm, card_85x54mm)"
    )
    calibration_confidence: Optional[float] = Field(
        None, description="Optical calibration confidence score"
    )
    # Relative prominence fallback for uncalibrated scans (Section 5)
    relative_prominence_flag: bool = Field(
        False, description="True if text height is disproportionately smaller than others on same panel"
    )
    relative_prominence_note: Optional[str] = Field(
        None, description="Informational readability note on relative text prominence"
    )
    required_font_height_mm: Optional[float] = Field(
        None, description="Minimum required font height per Rule 7(2) Table-I (None if PDP area unknown)"
    )
    pdp_area_cm2: Optional[float] = Field(
        None, description="Officer-supplied Principal Display Panel area used for the Rule 7(2) lookup"
    )
    confidence: Optional[float] = Field(
        None, description="OCR confidence for this detection"
    )
    # Placement validation (Rule 8(1) PDP compliance)
    placement_compliant: bool = Field(
        True, description="Does this declaration comply with Rule 8(1) placement rules?"
    )
    placement_violations: List[str] = Field(
        default_factory=list,
        description="Placement-specific violations (e.g., not on PDP, scattered)",
    )
    bbox_center: Optional[List[float]] = Field(
        None, description="[x, y] center of the bounding box for spatial analysis"
    )
    placement_review_required: bool = Field(
        False, description="Flagged for manual officer review if surface curvature or geometry confidence is low"
    )
    placement_review_reason: Optional[str] = Field(
        None, description="Reason why placement is flagged for manual officer verification"
    )
    price_review_required: bool = Field(
        False, description="Flagged for manual officer review if conflicting MRPs are detected on the package"
    )
    price_review_reason: Optional[str] = Field(
        None, description="Details of the conflicting MRP declarations"
    )
    note: Optional[str] = Field(
        None, description="Why a declaration is not required on this package (e.g. country of origin on a domestic product)"
    )


class PhotoEvidence(BaseModel):
    """One photo of a multi-photo product inspection, hashed on its raw uploaded bytes."""
    filename: str
    image_hash_sha256: str
    calibration_method: str = Field(..., description="aruco_40mm when the marker was found, else none")
    pixels_per_mm: Optional[float] = None
    ocr_regions: int = Field(0, description="Number of text regions read from this photo")


class ComplianceReport(BaseModel):
    """Full compliance report for a scanned label."""
    scan_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this scan",
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the scan was performed",
    )
    image_filename: str
    product_name: Optional[str] = Field(None, description="Product name entered by the inspecting officer")
    image_hash_sha256: Optional[str] = Field(
        None, description="SHA-256 evidence integrity hash of uploaded image"
    )
    dpi_used: int = Field(..., description="DPI equivalent used for pixel conversion")
    calibration_method: Optional[str] = Field(
        None, description="Physical calibration reference method (e.g. aruco_40mm, none)"
    )
    pixels_per_mm: Optional[float] = Field(
        None, description="Physical pixels per millimeter scale factor"
    )
    calibration_confidence: Optional[float] = Field(
        None, description="Confidence in optical calibration scale"
    )
    pre_capture_status: Optional[str] = Field(
        None, description="Pre-capture quality status (e.g. marker_detected_ready, no_marker_quick_scan)"
    )
    overall_compliant: bool = Field(
        ..., description="True only if ALL required fields are compliant"
    )
    placement_review_required: bool = Field(
        False, description="True if any mandatory declaration placement is flagged for manual officer review"
    )
    font_review_required: bool = Field(
        False, description="True if any font measurement is flagged for manual review"
    )
    coverage_review_required: bool = Field(
        False, description="True if low OCR coverage precludes confirming absence of any declaration"
    )
    relative_prominence_notes: List[str] = Field(
        default_factory=list,
        description="Informational intra-panel prominence notes for uncalibrated scans",
    )
    cross_panel_mismatches: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Cross-panel declaration conflicts across multi-image scans",
    )
    technical_verification_coverage: Optional[float] = Field(
        None, description="Reframed compliance coverage score (0-100%)"
    )
    total_fields: int
    compliant_fields: int
    non_compliant_fields: int
    declarations: List[DeclarationField]
    raw_ocr_results: List[OCRResult] = Field(
        default_factory=list,
        description="All raw OCR detections from the image",
    )
    summary: str = Field(
        ..., description="Human-readable compliance summary"
    )
    photos: List[PhotoEvidence] = Field(
        default_factory=list,
        description="Every photo of a multi-photo product inspection (empty for single-photo scans)",
    )

