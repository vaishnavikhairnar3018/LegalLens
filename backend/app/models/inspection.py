"""
LenseScan Inspection Model.
SQLAlchemy ORM model for storing label scans and legal compliance audit trail.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    Float,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Inspection(Base):
    """
    Persistent audit record of a packaged commodity label inspection.
    Includes cryptographic SHA-256 evidence hash for chain-of-custody.
    """

    __tablename__ = "inspections"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    officer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    image_filename = Column(String(255), nullable=False)
    # Product name as entered by the inspecting officer (null for older records)
    product_name = Column(String(200), nullable=True)
    image_hash_sha256 = Column(String(64), nullable=False, index=True)
    
    overall_compliant = Column(Boolean, nullable=False, index=True)
    total_fields = Column(Integer, nullable=False, default=8)
    compliant_fields = Column(Integer, nullable=False, default=0)
    non_compliant_fields = Column(Integer, nullable=False, default=0)
    
    summary = Column(Text, nullable=False)
    declarations_json = Column(Text, nullable=False)
    raw_ocr_json = Column(Text, nullable=True)
    dpi_used = Column(Integer, default=300, nullable=False)

    # Physical Calibration & Uncertainty Provenance (Section 4, 5, 6)
    calibration_method = Column(String(50), nullable=True)
    reference_size_mm = Column(Float, nullable=True)
    pixels_per_mm = Column(Float, nullable=True)
    calibration_confidence = Column(Float, nullable=True)
    font_uncertainty_mm = Column(Float, nullable=True)
    font_review_required = Column(Boolean, default=False, nullable=True)
    coverage_review_required = Column(Boolean, default=False, nullable=True)
    relative_prominence_json = Column(Text, nullable=True)
    cross_panel_mismatches_json = Column(Text, nullable=True)
    technical_verification_coverage = Column(Float, nullable=True)
    # Multi-photo product inspections: JSON list of {filename, image_hash_sha256,
    # calibration_method, pixels_per_mm}, one entry per photo, hashed on raw bytes.
    # Null for single-photo inspections (image_filename / image_hash_sha256 cover those).
    evidence_json = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # Relationships
    officer = relationship("User", back_populates="inspections")

    def __repr__(self) -> str:
        status = "COMPLIANT" if self.overall_compliant else "NON-COMPLIANT"
        return f"<Inspection(id='{self.id}', status='{status}', file='{self.image_filename}')>"
