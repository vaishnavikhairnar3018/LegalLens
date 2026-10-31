"""
LenseScan Scan Router.
Secure image upload endpoint with full OCR → Classification → Rule Engine pipeline.
"""

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import get_current_user, require_role
from app.database import get_db
from app.models.user import User
from app.models.inspection import Inspection
from app.config import get_settings
from app.utils.sanitizer import clean_product_name, sanitize_filename, validate_image_content
from app.services.image_preprocess import preprocess_image, get_dpi_from_image, normalize_upload
from app.services.ocr_pipeline import extract_text
from app.services.declaration_classifier import classify_declarations
from app.services.rule_engine import validate_compliance, generate_summary
from app.services.calibration import calibrate_image, check_pre_capture_quality
from app.services.cross_panel import check_cross_panel_consistency
from app.services.product_combine import PhotoResult, combine_photo_results
from app.schemas.scan import ComplianceReport, PhotoEvidence

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/scan", tags=["Compliance Scanning"])

# Allowed MIME types for upload
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/jpg"}


@router.post("/", response_model=ComplianceReport)
async def scan_label(
    image: UploadFile = File(
        ...,
        description="Product label image (JPEG or PNG, max 10MB)",
    ),
    pdp_area_cm2: Optional[float] = Form(
        None,
        gt=0,
        le=1_000_000,
        description="Principal Display Panel area in cm² (selects the Rule 7(2) minimum font height)",
    ),
    product_name: Optional[str] = Form(None, max_length=200, description="Product name entered by the officer"),
    current_user: User = Depends(require_role(["officer", "admin", "supervisor"])),
    db: AsyncSession = Depends(get_db),
):
    """
    Scan a packaged commodity label for LMPC Rules 2011 compliance.

    Pipeline:
    1. Validate file type and size
    2. Compute SHA-256 tamper-evident evidence hash
    3. Preprocess image (deskew, denoise, enhance)
    4. Extract text via EasyOCR (text, bounding boxes, font heights)
    5. Classify declarations (MRP, net qty, dates, manufacturer, etc.)
    6. Validate against LMPC rules (presence, format, font size)
    7. Persist inspection record into database for audit trail
    8. Return structured compliance report
    """
    logger.info(
        f"Scan request from user '{current_user.username}' "
        f"(role: {current_user.role})"
    )

    # ── Step 1: Validate upload ──
    if image.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {image.content_type}. "
            f"Only JPEG and PNG are allowed.",
        )

    file_bytes = await image.read()

    if len(file_bytes) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum of {settings.MAX_UPLOAD_SIZE_MB}MB.",
        )

    detected_mime = validate_image_content(file_bytes)
    if detected_mime is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content does not match a valid image format. "
            "The file may be corrupted or disguised.",
        )

    safe_filename = sanitize_filename(image.filename or "upload.jpg")
    name = clean_product_name(product_name)
    
    # ── Step 2: Compute SHA-256 evidence integrity hash ──
    image_hash = hashlib.sha256(file_bytes).hexdigest()
    logger.info(f"Processing image: {safe_filename} ({len(file_bytes)} bytes, SHA-256: {image_hash[:16]}...)")

    try:
        # One server-side resize; calibration and OCR both use it (the hash above is on the raw upload).
        work_bytes = normalize_upload(file_bytes)

        # ── Step 3: Optical Calibration & Scale Recovery (Section 3 & 4) ──
        calibration = calibrate_image(work_bytes)
        if calibration.pixels_per_mm:
            dpi = int(round(calibration.pixels_per_mm * 25.4))
            logger.info(f"Physical scale recovered via {calibration.calibration_method}: {calibration.pixels_per_mm:.2f} px/mm (equiv DPI: {dpi})")
        else:
            dpi = get_dpi_from_image(file_bytes, default_dpi=settings.DEFAULT_DPI)
            logger.info(f"Uncalibrated scan. EXIF/fallback DPI: {dpi}")

        preprocessed = preprocess_image(work_bytes)

        # ── Step 4: OCR extraction ──
        ocr_results = extract_text(
            preprocessed,
            dpi=dpi,
            languages=settings.ocr_languages_list,
        )
        logger.info(f"OCR extracted {len(ocr_results)} text regions")

        inspection_id = str(uuid.uuid4())
        scan_time = datetime.now(timezone.utc)

        if not ocr_results:
            empty_summary = (
                "❌ No text detected on the label. "
                "The image may be too blurry, too dark, or not a label."
            )
            # Save inspection record
            db_inspection = Inspection(
                id=inspection_id,
                officer_id=current_user.id,
                image_filename=safe_filename,
                product_name=name,
                image_hash_sha256=image_hash,
                overall_compliant=False,
                total_fields=8,
                compliant_fields=0,
                non_compliant_fields=8,
                summary=empty_summary,
                declarations_json=json.dumps([]),
                raw_ocr_json=json.dumps([]),
                dpi_used=dpi,
                calibration_method=calibration.calibration_method,
                reference_size_mm=calibration.reference_size_mm,
                pixels_per_mm=calibration.pixels_per_mm,
                calibration_confidence=calibration.calibration_confidence,
                font_review_required=False,
                coverage_review_required=False,
                relative_prominence_json=json.dumps([]),
                cross_panel_mismatches_json=json.dumps([]),
                technical_verification_coverage=0.0,
                created_at=scan_time,
            )
            db.add(db_inspection)
            await db.commit()

            return ComplianceReport(
                scan_id=inspection_id,
                timestamp=scan_time,
                image_filename=safe_filename,
                product_name=name,
                image_hash_sha256=image_hash,
                dpi_used=dpi,
                calibration_method=calibration.calibration_method,
                pixels_per_mm=calibration.pixels_per_mm,
                calibration_confidence=calibration.calibration_confidence,
                pre_capture_status=calibration.quality_gate.status_code,
                overall_compliant=False,
                placement_review_required=False,
                font_review_required=False,
                coverage_review_required=False,
                relative_prominence_notes=[],
                cross_panel_mismatches=[],
                technical_verification_coverage=0.0,
                total_fields=8,
                compliant_fields=0,
                non_compliant_fields=8,
                declarations=[],
                raw_ocr_results=[],
                summary=empty_summary,
            )

        # ── Step 5: Classify declarations ──
        declarations = classify_declarations(ocr_results)
        logger.info(
            f"Classified: {sum(1 for d in declarations.values() if d['detected'])}"
            f"/{len(declarations)} fields detected"
        )

        # ── Step 6: Validate against LMPC rules (with calibration + uncertainty) ──
        validation_results = validate_compliance(
            declarations,
            ocr_results,
            calibration_result=calibration,
            pdp_area_cm2=pdp_area_cm2,
        )

        has_placement_review = any(d.placement_review_required for d in validation_results)
        has_font_review = any(d.font_review_required for d in validation_results)
        has_coverage_review = any(d.coverage_review_required for d in validation_results)
        has_price_review = any(d.price_review_required for d in validation_results)
        has_any_review = has_placement_review or has_font_review or has_coverage_review or has_price_review

        # Truly compliant declarations are verified and free of pending review flags
        verified_compliant_count = sum(
            1 for r in validation_results if r.compliant and not (
                r.coverage_review_required or r.placement_review_required
                or r.font_review_required or r.price_review_required
            )
        )
        non_compliant_count = sum(
            1 for r in validation_results if not r.compliant and not (
                r.coverage_review_required or r.placement_review_required
                or r.font_review_required or r.price_review_required
            )
        )
        overall_compliant = (verified_compliant_count == len(validation_results)) and not has_any_review

        summary = generate_summary(validation_results)
        prominence_notes = [d.relative_prominence_note for d in validation_results if d.relative_prominence_note]
        coverage_pct = round((verified_compliant_count / max(1, len(validation_results))) * 100.0, 1)

        # ── Step 7: Persist Inspection Record to Database ──
        declarations_dicts = [d.model_dump() for d in validation_results]
        db_inspection = Inspection(
            id=inspection_id,
            officer_id=current_user.id,
            image_filename=safe_filename,
            product_name=name,
            image_hash_sha256=image_hash,
            overall_compliant=overall_compliant,
            total_fields=len(validation_results),
            compliant_fields=verified_compliant_count,
            non_compliant_fields=non_compliant_count,
            summary=summary,
            declarations_json=json.dumps(declarations_dicts),
            raw_ocr_json=json.dumps([r.model_dump() for r in ocr_results]),
            dpi_used=dpi,
            calibration_method=calibration.calibration_method,
            reference_size_mm=calibration.reference_size_mm,
            pixels_per_mm=calibration.pixels_per_mm,
            calibration_confidence=calibration.calibration_confidence,
            font_review_required=has_font_review,
            coverage_review_required=has_coverage_review,
            relative_prominence_json=json.dumps(prominence_notes),
            cross_panel_mismatches_json=json.dumps([]),
            technical_verification_coverage=coverage_pct,
            created_at=scan_time,
        )
        db.add(db_inspection)
        await db.commit()

        # ── Step 8: Return report ──
        report = ComplianceReport(
            scan_id=inspection_id,
            timestamp=scan_time,
            image_filename=safe_filename,
            product_name=name,
            image_hash_sha256=image_hash,
            dpi_used=dpi,
            calibration_method=calibration.calibration_method,
            pixels_per_mm=calibration.pixels_per_mm,
            calibration_confidence=calibration.calibration_confidence,
            pre_capture_status=calibration.quality_gate.status_code,
            overall_compliant=overall_compliant,
            placement_review_required=has_placement_review,
            font_review_required=has_font_review,
            coverage_review_required=has_coverage_review,
            relative_prominence_notes=prominence_notes,
            cross_panel_mismatches=[],
            technical_verification_coverage=coverage_pct,
            total_fields=len(validation_results),
            compliant_fields=verified_compliant_count,
            non_compliant_fields=non_compliant_count,
            declarations=validation_results,
            raw_ocr_results=ocr_results,
            summary=summary,
        )

        logger.info(
            f"Scan recorded (ID: {inspection_id}) for '{safe_filename}': "
            f"{'COMPLIANT' if overall_compliant else 'NON-COMPLIANT'} "
            f"({verified_compliant_count}/{len(validation_results)})"
        )

        return report

    except ValueError as e:
        logger.error(f"Image processing error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image processing failed: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Scan pipeline error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred during label scanning. "
            "Please try again or contact support.",
        )


MAX_PRODUCT_PHOTOS = 8


async def _read_validated_image(upload: UploadFile) -> bytes:
    """Read one uploaded photo and apply the same checks as the single-photo scan."""
    if upload.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type for {upload.filename}: {upload.content_type}. Only JPEG and PNG are allowed.",
        )
    data = await upload.read()
    if len(data) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"{upload.filename} exceeds the maximum of {settings.MAX_UPLOAD_SIZE_MB}MB.",
        )
    if validate_image_content(data) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{upload.filename} is not a valid image. It may be corrupted or disguised.",
        )
    return data


@router.post("/product", response_model=ComplianceReport)
async def scan_product(
    images: List[UploadFile] = File(..., description="1 to 8 photos of the same product (clean and/or with the 40 mm marker)"),
    pdp_area_cm2: Optional[float] = Form(
        None,
        gt=0,
        le=1_000_000,
        description="Principal Display Panel area in cm² (selects the Rule 7(2) minimum font height)",
    ),
    product_name: Optional[str] = Form(None, max_length=200, description="Product name entered by the officer"),
    current_user: User = Depends(require_role(["officer", "admin", "supervisor"])),
    db: AsyncSession = Depends(get_db),
):
    """
    One inspection from several photos of one product.

    Each photo is hashed (raw bytes), checked for the ArUco marker, read by OCR and checked
    against the rules on its own. The results are then combined per declaration: taken from a
    photo with the marker when found there (font size measured), otherwise from a photo without
    the marker (font size goes to officer review). Missing only if no photo shows it.
    Roles: officer, supervisor, admin. The record belongs to the officer who scanned it.
    """
    if not images:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Add at least one photo.")
    if len(images) > MAX_PRODUCT_PHOTOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"At most {MAX_PRODUCT_PHOTOS} photos per product.",
        )

    # Validate and hash every photo before any processing (evidence chain).
    uploads = []
    for upload in images:
        data = await _read_validated_image(upload)
        uploads.append((sanitize_filename(upload.filename or "photo.jpg"), data, hashlib.sha256(data).hexdigest()))

    try:
        photo_results: List[PhotoResult] = []
        evidence: List[PhotoEvidence] = []
        all_ocr: List[Dict[str, Any]] = []
        for name, data, digest in uploads:
            # One server-side resize; calibration and OCR both use it (digest is of the raw upload).
            work = normalize_upload(data)
            calibration = calibrate_image(work)
            dpi = (
                int(round(calibration.pixels_per_mm * 25.4))
                if calibration.pixels_per_mm
                else get_dpi_from_image(data, default_dpi=settings.DEFAULT_DPI)
            )
            ocr_results = extract_text(preprocess_image(work), dpi=dpi, languages=settings.ocr_languages_list)
            fields = validate_compliance(
                classify_declarations(ocr_results),
                ocr_results,
                calibration_result=calibration,
                pdp_area_cm2=pdp_area_cm2,
            )
            photo_results.append(PhotoResult(label=name, calibrated=bool(calibration.pixels_per_mm), fields=fields))
            evidence.append(PhotoEvidence(
                filename=name,
                image_hash_sha256=digest,
                calibration_method=calibration.calibration_method,
                pixels_per_mm=calibration.pixels_per_mm,
                ocr_regions=len(ocr_results),
            ))
            all_ocr.append({"filename": name, "ocr": [r.model_dump() for r in ocr_results]})
            logger.info(f"Product photo {name}: {calibration.calibration_method}, {len(ocr_results)} text regions")
    except ValueError as e:
        logger.error(f"Image processing error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Image processing failed: {e}")
    except Exception as e:
        logger.error(f"Product scan pipeline error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while checking the photos. Please try again.",
        )

    combined = combine_photo_results(photo_results)
    # Different values for the same declaration across photos (e.g. two MRPs) need an officer.
    mismatches = check_cross_panel_consistency(
        [{"panel_id": p.label, "declarations": p.fields} for p in photo_results]
    )

    def under_review(r) -> bool:
        return r.coverage_review_required or r.placement_review_required or r.font_review_required or r.price_review_required

    has_font_review = any(d.font_review_required for d in combined)
    has_coverage_review = any(d.coverage_review_required for d in combined)
    has_placement_review = any(d.placement_review_required for d in combined)
    verified = sum(1 for r in combined if r.compliant and not under_review(r))
    hard_fail = sum(1 for r in combined if not r.compliant and not under_review(r))
    any_review = any(under_review(r) for r in combined) or bool(mismatches)
    overall_compliant = verified == len(combined) and not any_review

    summary = generate_summary(combined)
    if mismatches:
        summary += "\n\n" + "\n".join(f"🔍 PHOTOS DISAGREE: {m['description']}" for m in mismatches)
    prominence = [d.relative_prominence_note for d in combined if d.relative_prominence_note]
    coverage_pct = round(verified / max(1, len(combined)) * 100.0, 1)
    marker = next((e for e in evidence if e.pixels_per_mm), None)
    inspection_id = str(uuid.uuid4())
    scan_time = datetime.now(timezone.utc)
    filenames = ", ".join(e.filename for e in evidence)

    name = clean_product_name(product_name)
    db.add(Inspection(
        id=inspection_id,
        officer_id=current_user.id,
        product_name=name,
        image_filename=filenames[:255],
        image_hash_sha256=evidence[0].image_hash_sha256,  # every photo's hash is in evidence_json
        overall_compliant=overall_compliant,
        total_fields=len(combined),
        compliant_fields=verified,
        non_compliant_fields=hard_fail,
        summary=summary,
        declarations_json=json.dumps([d.model_dump() for d in combined]),
        raw_ocr_json=json.dumps(all_ocr),
        dpi_used=int(round(marker.pixels_per_mm * 25.4)) if marker else settings.DEFAULT_DPI,
        calibration_method=marker.calibration_method if marker else "none",
        pixels_per_mm=marker.pixels_per_mm if marker else None,
        font_review_required=has_font_review,
        coverage_review_required=has_coverage_review,
        relative_prominence_json=json.dumps(prominence),
        cross_panel_mismatches_json=json.dumps(mismatches),
        technical_verification_coverage=coverage_pct,
        evidence_json=json.dumps([e.model_dump() for e in evidence]),
        created_at=scan_time,
    ))
    await db.commit()

    logger.info(
        f"Product inspection {inspection_id}: {len(evidence)} photos, "
        f"{'COMPLIANT' if overall_compliant else 'NON-COMPLIANT'} ({verified}/{len(combined)})"
    )
    return ComplianceReport(
        scan_id=inspection_id,
        timestamp=scan_time,
        image_filename=filenames,
        product_name=name,
        image_hash_sha256=evidence[0].image_hash_sha256,
        dpi_used=int(round(marker.pixels_per_mm * 25.4)) if marker else settings.DEFAULT_DPI,
        calibration_method=marker.calibration_method if marker else "none",
        pixels_per_mm=marker.pixels_per_mm if marker else None,
        overall_compliant=overall_compliant,
        placement_review_required=has_placement_review,
        font_review_required=has_font_review,
        coverage_review_required=has_coverage_review,
        relative_prominence_notes=prominence,
        cross_panel_mismatches=mismatches,
        technical_verification_coverage=coverage_pct,
        total_fields=len(combined),
        compliant_fields=verified,
        non_compliant_fields=hard_fail,
        declarations=combined,
        summary=summary,
        photos=evidence,
    )


@router.post("/pre-capture")
async def pre_capture_check(
    image: UploadFile = File(..., description="Preview frame image for blur/glare inspection"),
    current_user: User = Depends(require_role(["officer", "admin", "supervisor"])),
):
    """
    Lightweight optical quality gate check before taking final scan.
    Returns status: marker_detected_ready | no_marker_quick_scan | marker_detected_but_low_quality
    """
    file_bytes = await image.read()
    try:
        cal = calibrate_image(normalize_upload(file_bytes))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {
        "status_code": cal.quality_gate.status_code,
        "is_blurry": cal.quality_gate.is_blurry,
        "laplacian_variance": cal.quality_gate.laplacian_variance,
        "marker_has_glare": cal.quality_gate.marker_has_glare,
        "glare_pixel_ratio": cal.quality_gate.glare_pixel_ratio,
        "calibration_method": cal.calibration_method,
        "calibration_status": cal.calibration_status,
        "user_prompt": cal.quality_gate.user_prompt,
    }


@router.post("/multi-panel")
async def scan_multi_panel(
    images: List[UploadFile] = File(..., description="Multiple panel images of a product package"),
    pdp_area_cm2: Optional[float] = Form(
        None,
        gt=0,
        le=1_000_000,
        description="Principal Display Panel area in cm² (selects the Rule 7(2) minimum font height)",
    ),
    current_user: User = Depends(require_role(["officer", "admin", "supervisor"])),
    db: AsyncSession = Depends(get_db),
):
    """
    Multi-image compliance scan across multiple panels (e.g. Front PDP + Back Info Panel).
    Detects cross-panel contradictory declarations (MRP, net quantity, mfg dates).
    """
    if not images or len(images) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least 2 panel images are required for multi-panel inspection.",
        )

    panel_reports = []
    panel_items_for_cross_check = []

    for idx, img in enumerate(images):
        panel_id = f"panel_{idx + 1}_{sanitize_filename(img.filename or 'img.jpg')}"
        file_bytes = await img.read()
        image_hash = hashlib.sha256(file_bytes).hexdigest()

        try:
            work_bytes = normalize_upload(file_bytes)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{panel_id}: {e}")
        cal = calibrate_image(work_bytes)
        dpi = int(round(cal.pixels_per_mm * 25.4)) if cal.pixels_per_mm else settings.DEFAULT_DPI
        preprocessed = preprocess_image(work_bytes)
        ocr_results = extract_text(preprocessed, dpi=dpi, languages=settings.ocr_languages_list)
        declarations = classify_declarations(ocr_results)
        validation_results = validate_compliance(
            declarations, ocr_results, calibration_result=cal, pdp_area_cm2=pdp_area_cm2
        )

        compliant_count = sum(1 for r in validation_results if r.compliant)
        non_compliant_count = len(validation_results) - compliant_count
        overall_compliant = compliant_count == len(validation_results)
        summary = generate_summary(validation_results)
        inspection_id = str(uuid.uuid4())
        scan_time = datetime.now(timezone.utc)

        panel_reports.append({
            "panel_id": panel_id,
            "scan_id": inspection_id,
            "filename": img.filename,
            "image_hash": image_hash,
            "calibration_method": cal.calibration_method,
            "pixels_per_mm": cal.pixels_per_mm,
            "overall_compliant": overall_compliant,
            "declarations": validation_results,
            "summary": summary,
        })
        panel_items_for_cross_check.append({
            "panel_id": panel_id,
            "declarations": validation_results,
        })

    mismatches = check_cross_panel_consistency(panel_items_for_cross_check)

    return {
        "multi_panel_compliant": len(mismatches) == 0 and all(p["overall_compliant"] for p in panel_reports),
        "total_panels": len(panel_reports),
        "cross_panel_mismatches": mismatches,
        "panels": panel_reports,
    }
