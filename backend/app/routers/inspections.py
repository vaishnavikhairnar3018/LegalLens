"""
LenseScan Inspections Router.
Endpoints for retrieving past inspection audit records and generating official legal notice PDFs.
"""

import csv
import io
import json
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.database import get_db
from app.models.user import User, UserRole
from app.models.inspection import Inspection
from app.core.rbac import get_current_user, require_role
from app.services.pdf_report_generator import generate_inspection_pdf
from app.services.docx_report_generator import generate_inspection_docx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inspections", tags=["Inspection Audit Trail"])


@router.get("/", response_model=List[dict])
async def list_inspections(
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Page limit"),
    compliant_only: Optional[bool] = Query(None, description="Filter by compliance"),
    current_user: User = Depends(require_role(["officer", "admin", "supervisor"])),
    db: AsyncSession = Depends(get_db),
):
    """
    List past commodity inspections for audit trail and history.
    - Officers see their own inspections.
    - Supervisors and Admins see all inspections across the department.
    """
    stmt = select(Inspection).order_by(desc(Inspection.created_at))

    # RBAC filtering: Officers only see their own inspections
    if current_user.role == UserRole.OFFICER:
        stmt = stmt.where(Inspection.officer_id == current_user.id)

    if compliant_only is not None:
        stmt = stmt.where(Inspection.overall_compliant == compliant_only)

    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    inspections = result.scalars().all()

    return [
        {
            "id": insp.id,
            "officer_id": insp.officer_id,
            "image_filename": insp.image_filename,
            "product_name": insp.product_name,
            "image_hash_sha256": insp.image_hash_sha256,
            "overall_compliant": insp.overall_compliant,
            "total_fields": insp.total_fields,
            "compliant_fields": insp.compliant_fields,
            "non_compliant_fields": insp.non_compliant_fields,
            "placement_review_required": bool(insp.font_review_required or insp.coverage_review_required or (insp.calibration_confidence is not None and insp.calibration_confidence < 0.6)),
            "font_review_required": bool(insp.font_review_required),
            "coverage_review_required": bool(insp.coverage_review_required),
            "summary": insp.summary,
            "created_at": insp.created_at.isoformat(),
        }
        for insp in inspections
    ]


@router.get("/{inspection_id}", response_model=dict)
async def get_inspection_detail(
    inspection_id: str,
    current_user: User = Depends(require_role(["officer", "admin", "supervisor"])),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve full inspection details including all individual declaration field checks.
    """
    stmt = select(Inspection).where(Inspection.id == inspection_id)
    result = await db.execute(stmt)
    insp = result.scalar_one_or_none()

    if not insp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inspection record '{inspection_id}' not found.",
        )

    # RBAC check: officer can only view own inspection
    if current_user.role == UserRole.OFFICER and insp.officer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view another officer's inspection.",
        )

    return {
        "id": insp.id,
        "officer_id": insp.officer_id,
        "image_filename": insp.image_filename,
        "product_name": insp.product_name,
        "image_hash_sha256": insp.image_hash_sha256,
        "overall_compliant": insp.overall_compliant,
        "total_fields": insp.total_fields,
        "compliant_fields": insp.compliant_fields,
        "non_compliant_fields": insp.non_compliant_fields,
        "summary": insp.summary,
        "dpi_used": insp.dpi_used,
        "declarations": json.loads(insp.declarations_json),
        "photos": _photos(insp),
        "created_at": insp.created_at.isoformat(),
    }


def _photos(insp: Inspection) -> list:
    """Every photo of a product inspection with its evidence hash ([] for single-photo scans)."""
    return json.loads(insp.evidence_json) if insp.evidence_json else []


@router.get("/{inspection_id}/notice.pdf")
async def download_inspection_notice(
    inspection_id: str,
    current_user: User = Depends(require_role(["officer", "admin", "supervisor"])),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate and download the official Ministry of Consumer Affairs Form LM-N1
    Statutory Non-Compliance Notice or Form LM-C1 Compliance Certificate.
    """
    stmt = select(Inspection).where(Inspection.id == inspection_id)
    result = await db.execute(stmt)
    insp = result.scalar_one_or_none()

    if not insp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inspection record '{inspection_id}' not found.",
        )

    # RBAC check
    if current_user.role == UserRole.OFFICER and insp.officer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this legal notice.",
        )

    declarations = json.loads(insp.declarations_json)

    pdf_bytes = generate_inspection_pdf(
        inspection_id=insp.id,
        officer_name=current_user.full_name or current_user.username,
        officer_id=insp.officer_id,
        image_filename=insp.image_filename,
        image_hash_sha256=insp.image_hash_sha256,
        timestamp=insp.created_at,
        overall_compliant=insp.overall_compliant,
        total_fields=insp.total_fields,
        compliant_fields=insp.compliant_fields,
        non_compliant_fields=insp.non_compliant_fields,
        summary=insp.summary,
        declarations=declarations,
        photos=_photos(insp),
        product_name=insp.product_name,
    )

    filename = (
        f"LMPC_Notice_{insp.id[:8]}.pdf"
        if not insp.overall_compliant
        else f"LMPC_Certificate_{insp.id[:8]}.pdf"
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store, no-cache, must-revalidate",
        },
    )


@router.get("/{inspection_id}/notice.docx")
async def download_inspection_notice_docx(
    inspection_id: str,
    current_user: User = Depends(require_role(["officer", "admin", "supervisor"])),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate and download an editable Word document (DOCX) version of the
    inspection report. Required by SIH 26034: 'reports in PDF and editable formats.'
    """
    stmt = select(Inspection).where(Inspection.id == inspection_id)
    result = await db.execute(stmt)
    insp = result.scalar_one_or_none()

    if not insp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inspection record '{inspection_id}' not found.",
        )

    if current_user.role == UserRole.OFFICER and insp.officer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this record.",
        )

    declarations = json.loads(insp.declarations_json)

    docx_bytes = generate_inspection_docx(
        inspection_id=insp.id,
        officer_name=current_user.full_name or current_user.username,
        officer_id=insp.officer_id,
        image_filename=insp.image_filename,
        image_hash_sha256=insp.image_hash_sha256,
        timestamp=insp.created_at,
        overall_compliant=insp.overall_compliant,
        total_fields=insp.total_fields,
        compliant_fields=insp.compliant_fields,
        non_compliant_fields=insp.non_compliant_fields,
        summary=insp.summary,
        declarations=declarations,
        photos=_photos(insp),
        product_name=insp.product_name,
    )

    filename = (
        f"LMPC_Notice_{insp.id[:8]}.docx"
        if not insp.overall_compliant
        else f"LMPC_Certificate_{insp.id[:8]}.docx"
    )

    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store, no-cache, must-revalidate",
        },
    )


@router.get("/{inspection_id}/export.json")
async def export_inspection_json(
    inspection_id: str,
    current_user: User = Depends(require_role(["officer", "admin", "supervisor"])),
    db: AsyncSession = Depends(get_db),
):
    """
    Full machine-readable JSON export of an inspection record.
    """
    stmt = select(Inspection).where(Inspection.id == inspection_id)
    result = await db.execute(stmt)
    insp = result.scalar_one_or_none()

    if not insp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inspection record '{inspection_id}' not found.",
        )

    if current_user.role == UserRole.OFFICER and insp.officer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )

    export_data = {
        "id": insp.id,
        "officer_id": insp.officer_id,
        "image_filename": insp.image_filename,
        "product_name": insp.product_name,
        "image_hash_sha256": insp.image_hash_sha256,
        "overall_compliant": insp.overall_compliant,
        "total_fields": insp.total_fields,
        "compliant_fields": insp.compliant_fields,
        "non_compliant_fields": insp.non_compliant_fields,
        "summary": insp.summary,
        "dpi_used": insp.dpi_used,
        "declarations": json.loads(insp.declarations_json),
        "photos": _photos(insp),
        "created_at": insp.created_at.isoformat(),
    }

    json_content = json.dumps(export_data, indent=2, ensure_ascii=False)

    return Response(
        content=json_content.encode("utf-8"),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="LMPC_Inspection_{insp.id[:8]}.json"',
        },
    )


@router.get("/export/all.csv")
async def export_all_inspections_csv(
    current_user: User = Depends(require_role(["admin", "supervisor"])),
    db: AsyncSession = Depends(get_db),
):
    """
    Batch CSV export of all inspections for department-wide audit spreadsheets.
    Available only to Admins and Supervisors.
    """
    stmt = select(Inspection).order_by(Inspection.created_at.desc())
    result = await db.execute(stmt)
    inspections = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Inspection ID", "Officer ID", "Product Name", "Image Filename", "SHA-256 Hash",
        "Compliant", "Total Fields", "Compliant Fields", "Non-Compliant Fields",
        "Summary", "DPI", "Created At",
    ])

    for insp in inspections:
        writer.writerow([
            insp.id, insp.officer_id, insp.product_name or "", insp.image_filename,
            insp.image_hash_sha256, insp.overall_compliant,
            insp.total_fields, insp.compliant_fields,
            insp.non_compliant_fields, insp.summary,
            insp.dpi_used, insp.created_at.isoformat() if insp.created_at else "",
        ])

    csv_content = output.getvalue()
    output.close()

    return Response(
        content=csv_content.encode("utf-8"),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="LMPC_Inspections_Export.csv"',
        },
    )
