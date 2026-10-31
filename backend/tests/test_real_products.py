"""
Integration & Verification tests for Phase 2:
- Real product sample evaluation (SHA-256 evidence integrity hashing)
- PDF Generation (Form LM-N1 Statutory Non-Compliance Notice & Form LM-C1 Inspection Certificate)
- Inspection DB persistence and API endpoint retrieval
"""

import hashlib
import json
import os
import pytest
from datetime import datetime, timezone
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.database import Base, get_db
from app.models.user import User, UserRole
from app.models.inspection import Inspection
from app.services.pdf_report_generator import generate_inspection_pdf
from app.services.docx_report_generator import generate_inspection_docx
from app.core.security import create_access_token, get_password_hash


# In-memory SQLite async engine for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

test_async_session = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(name="db_session")
async def db_session_fixture():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with test_async_session() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(name="client")
async def client_fixture(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(name="test_officer")
async def test_officer_fixture(db_session: AsyncSession):
    user = User(
        username="officer_verma",
        full_name="Rajesh Verma, Legal Metrology Officer",
        hashed_password=get_password_hash("securepass123"),
        role=UserRole.OFFICER,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture(name="test_admin")
async def test_admin_fixture(db_session: AsyncSession):
    user = User(
        username="admin_singh",
        full_name="Director Singh, Enforcement Head",
        hashed_password=get_password_hash("adminpass123"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


def _sample_declarations(is_compliant: bool = False):
    violations = []
    if not is_compliant:
        violations = ["Net quantity declaration missing numerical value under Rule 12."]

    return [
        {
            "field_name": "mrp",
            "detected": True,
            "value": "Rs. 110.00",
            "font_height_mm": 2.5,
            "min_font_mm": 1.0,
            "compliant": True,
            "violations": [],
            "legal_rule": "Rule 6(1)(e)",
        },
        {
            "field_name": "net_quantity",
            "detected": not is_compliant,
            "value": "" if not is_compliant else "500 ml",
            "font_height_mm": 0.0 if not is_compliant else 2.5,
            "min_font_mm": 2.0,
            "compliant": is_compliant,
            "violations": violations,
            "legal_rule": "Rule 6(1)(c)",
        },
        {
            "field_name": "manufacturer_details",
            "detected": True,
            "value": "Suruchi Foods Pvt Ltd, Plot 42, MIDC, Nagpur",
            "font_height_mm": 2.0,
            "min_font_mm": 1.0,
            "compliant": True,
            "violations": [],
            "legal_rule": "Rule 6(1)(a)",
        },
        {
            "field_name": "consumer_care",
            "detected": True,
            "value": "care@suruchi.com / 1800-200-1122",
            "font_height_mm": 1.8,
            "min_font_mm": 1.0,
            "compliant": True,
            "violations": [],
            "legal_rule": "Rule 6(2)",
        },
    ]


def test_pdf_generation_violation_notice():
    """Verify Form LM-N1 Notice of Seizure / Section 36 Compound Notice generation."""
    declarations = _sample_declarations(is_compliant=False)
    pdf_bytes = generate_inspection_pdf(
        inspection_id="ins-test-non-compliant-001",
        officer_name="Inspector R. Verma",
        officer_id=1,
        image_filename="IMG_20260908_202736771.jpg",
        image_hash_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        timestamp=datetime.now(timezone.utc),
        overall_compliant=False,
        total_fields=8,
        compliant_fields=7,
        non_compliant_fields=1,
        summary="Statutory violation: Net quantity declaration missing numerical value.",
        declarations=declarations,
    )
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF-")


def test_pdf_product_name_with_markup_characters_is_escaped():
    """Officer-typed names may contain & or < >; the PDF must render them as text, not fail."""
    import io
    from pypdf import PdfReader

    name = "Haldiram's Aloo Bhujia & Co <Spl>"
    pdf_bytes = generate_inspection_pdf(
        inspection_id="esc-1",
        officer_name="Test Officer",
        officer_id=1,
        image_filename="a.jpg",
        image_hash_sha256="0" * 64,
        timestamp=datetime.now(timezone.utc),
        overall_compliant=False,
        total_fields=1,
        compliant_fields=0,
        non_compliant_fields=1,
        summary="x",
        declarations=_sample_declarations(is_compliant=False),
        product_name=name,
    )
    text = "".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf_bytes)).pages)
    assert name in text


def test_pdf_generation_certificate_of_compliance():
    """Verify Form LM-C1 Certificate of Compliance generation."""
    declarations = _sample_declarations(is_compliant=True)
    pdf_bytes = generate_inspection_pdf(
        inspection_id="ins-test-compliant-002",
        officer_name="Inspector R. Verma",
        officer_id=1,
        image_filename="balaji_simply_salted.jpg",
        image_hash_sha256="c555a12398fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        timestamp=datetime.now(timezone.utc),
        overall_compliant=True,
        total_fields=8,
        compliant_fields=8,
        non_compliant_fields=0,
        summary="All mandatory declarations compliant with Legal Metrology Rules, 2011.",
        declarations=declarations,
    )
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF-")


@pytest.mark.asyncio
async def test_inspection_persistence_and_endpoints(client: AsyncClient, db_session: AsyncSession, test_officer: User):
    """Test full DB lifecycle: storing Inspection record with SHA-256 hash and retrieving via API."""
    token = create_access_token(data={"sub": test_officer.username, "role": test_officer.role.value})
    headers = {"Authorization": f"Bearer {token}"}

    sample_sha = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
    inspection = Inspection(
        id="insp-uuid-9999",
        officer_id=test_officer.id,
        image_filename="IMG_20260908_202736771.jpg",
        image_hash_sha256=sample_sha,
        overall_compliant=False,
        total_fields=8,
        compliant_fields=7,
        non_compliant_fields=1,
        summary="Net quantity missing numerical value",
        declarations_json=json.dumps(_sample_declarations(is_compliant=False)),
        dpi_used=300,
    )
    db_session.add(inspection)
    await db_session.commit()
    await db_session.refresh(inspection)

    # 1. Test listing inspections
    res = await client.get("/api/v1/inspections/", headers=headers)
    assert res.status_code == 200
    items = res.json()
    assert len(items) >= 1
    assert items[0]["id"] == inspection.id
    assert items[0]["image_hash_sha256"] == sample_sha
    assert items[0]["overall_compliant"] is False

    # 2. Test fetching single inspection detail
    res_single = await client.get(f"/api/v1/inspections/{inspection.id}", headers=headers)
    assert res_single.status_code == 200
    single_data = res_single.json()
    assert single_data["id"] == inspection.id
    assert len(single_data["declarations"]) == 4

    # 3. Test streaming PDF report endpoint
    res_pdf = await client.get(f"/api/v1/inspections/{inspection.id}/notice.pdf", headers=headers)
    assert res_pdf.status_code == 200
    assert res_pdf.headers["content-type"] == "application/pdf"
    assert res_pdf.content.startswith(b"%PDF-")


def test_real_product_image_hash_integrity():
    """Verify cryptographic SHA-256 hashing on actual product images in d:\\LenseScan\\product."""
    product_dir = r"d:\LenseScan\product"
    if not os.path.exists(product_dir):
        pytest.skip("Product folder not found locally")

    images = [f for f in os.listdir(product_dir) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
    if not images:
        pytest.skip("No product images found")

    sample_path = os.path.join(product_dir, images[0])
    with open(sample_path, "rb") as f:
        file_bytes = f.read()

    computed_hash = hashlib.sha256(file_bytes).hexdigest()
    assert len(computed_hash) == 64
    assert all(c in "0123456789abcdef" for c in computed_hash)


def test_docx_generation_violation_notice():
    """Verify DOCX statutory notice generation."""
    declarations = _sample_declarations(is_compliant=False)
    docx_bytes = generate_inspection_docx(
        inspection_id="ins-test-docx-001",
        officer_name="Inspector R. Verma",
        officer_id=1,
        image_filename="biscuit_packet.jpg",
        image_hash_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        timestamp=datetime.now(timezone.utc),
        overall_compliant=False,
        total_fields=8,
        compliant_fields=7,
        non_compliant_fields=1,
        summary="Statutory violation: Net quantity declaration missing numerical value.",
        declarations=declarations,
    )
    assert isinstance(docx_bytes, bytes)
    assert len(docx_bytes) > 1000
    # DOCX is a zip file starting with PK\x03\x04
    assert docx_bytes.startswith(b"PK")


@pytest.mark.asyncio
async def test_docx_and_json_and_csv_export_endpoints(
    client: AsyncClient, db_session: AsyncSession, test_officer: User, test_admin: User
):
    """Verify DOCX, JSON, and CSV export endpoints."""
    officer_token = create_access_token(data={"sub": test_officer.username, "role": test_officer.role.value})
    officer_headers = {"Authorization": f"Bearer {officer_token}"}

    admin_token = create_access_token(data={"sub": test_admin.username, "role": test_admin.role.value})
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    inspection = Inspection(
        id="insp-export-test-101",
        officer_id=test_officer.id,
        image_filename="test_sample.jpg",
        image_hash_sha256="abcd1234ef567890abcd1234ef567890abcd1234ef567890abcd1234ef567890",
        overall_compliant=False,
        total_fields=8,
        compliant_fields=6,
        non_compliant_fields=2,
        summary="MRP missing taxes text; Net qty font size violation",
        declarations_json=json.dumps(_sample_declarations(is_compliant=False)),
        dpi_used=300,
    )
    db_session.add(inspection)
    await db_session.commit()

    # 1. DOCX export
    res_docx = await client.get(f"/api/v1/inspections/{inspection.id}/notice.docx", headers=officer_headers)
    assert res_docx.status_code == 200
    assert "wordprocessingml" in res_docx.headers["content-type"]
    assert res_docx.content.startswith(b"PK")

    # 2. JSON export
    res_json = await client.get(f"/api/v1/inspections/{inspection.id}/export.json", headers=officer_headers)
    assert res_json.status_code == 200
    export_body = res_json.json()
    assert export_body["id"] == inspection.id
    assert export_body["image_hash_sha256"] == inspection.image_hash_sha256
    assert len(export_body["declarations"]) == 4

    # 3. CSV export (Admin only)
    res_csv = await client.get("/api/v1/inspections/export/all.csv", headers=admin_headers)
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    assert "Inspection ID,Officer ID" in res_csv.text
    assert inspection.id in res_csv.text

    # 4. CSV export (Officer gets 403 Forbidden - Admin/Supervisor only)
    res_csv_officer = await client.get("/api/v1/inspections/export/all.csv", headers=officer_headers)
    assert res_csv_officer.status_code == 403
    assert "Access denied" in res_csv_officer.json()["detail"]


@pytest.mark.asyncio
async def test_dashboard_analytics_endpoints(
    client: AsyncClient, db_session: AsyncSession, test_officer: User, test_admin: User
):
    """Verify all aggregate dashboard analytics endpoints required by SIH 26034."""
    admin_token = create_access_token(data={"sub": test_admin.username, "role": test_admin.role.value})
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Add a sample inspection
    inspection = Inspection(
        id="insp-dash-001",
        officer_id=test_officer.id,
        image_filename="parle_g.jpg",
        image_hash_sha256="1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
        overall_compliant=False,
        total_fields=8,
        compliant_fields=5,
        non_compliant_fields=3,
        summary="3 violations detected",
        declarations_json=json.dumps(_sample_declarations(is_compliant=False)),
        dpi_used=300,
    )
    db_session.add(inspection)
    await db_session.commit()

    # 1. Summary KPIs
    res_summary = await client.get("/api/v1/dashboard/summary", headers=admin_headers)
    assert res_summary.status_code == 200
    summary_data = res_summary.json()
    assert "total_inspections" in summary_data
    assert "compliant_count" in summary_data
    assert "non_compliant_count" in summary_data
    assert "compliance_rate_pct" in summary_data
    assert "total_violation_flags" in summary_data
    assert summary_data["total_inspections"] >= 1

    # 2. Violations by Type
    res_violations = await client.get("/api/v1/dashboard/violations-by-type", headers=admin_headers)
    assert res_violations.status_code == 200
    violation_data = res_violations.json()
    assert "by_category" in violation_data
    assert "by_field" in violation_data
    assert "missing_declaration" in violation_data["by_category"]

    # 3. Trends
    res_trends = await client.get("/api/v1/dashboard/trends?days=7", headers=admin_headers)
    assert res_trends.status_code == 200
    trend_data = res_trends.json()
    assert "dates" in trend_data
    assert "totals" in trend_data
    assert "compliant" in trend_data
    assert "non_compliant" in trend_data

    # 4. Officer Activity
    res_officers = await client.get("/api/v1/dashboard/officer-activity", headers=admin_headers)
    assert res_officers.status_code == 200
    officer_data = res_officers.json()
    assert "officers" in officer_data
    assert any(o["username"] == test_officer.username for o in officer_data["officers"])


@pytest.mark.asyncio
async def test_officer_activity_scoped_to_self_and_role_restricted(
    client: AsyncClient, db_session: AsyncSession, test_officer: User, test_admin: User
):
    """
    Verify GET /api/v1/dashboard/officer-activity access boundaries:
    - Regular Officer sees ONLY their own statistics (other officers' records are excluded).
    - Admin/Supervisor sees the complete department-wide roster.
    - Unauthenticated request is rejected with 401.
    """
    # Create second officer
    officer2 = User(
        username="officer_sharma",
        full_name="Pooja Sharma, Legal Metrology Officer",
        hashed_password=get_password_hash("pass123"),
        role=UserRole.OFFICER,
        is_active=True,
    )
    db_session.add(officer2)
    await db_session.commit()
    await db_session.refresh(officer2)

    # Create inspections for both officers
    insp1 = Inspection(
        id="insp-verma-01",
        officer_id=test_officer.id,
        image_filename="verma_sample.jpg",
        image_hash_sha256="aa11" * 16,
        overall_compliant=True,
        total_fields=8,
        compliant_fields=8,
        non_compliant_fields=0,
        summary="All compliant",
        declarations_json=json.dumps([]),
        dpi_used=300,
    )
    insp2 = Inspection(
        id="insp-sharma-01",
        officer_id=officer2.id,
        image_filename="sharma_sample.jpg",
        image_hash_sha256="bb22" * 16,
        overall_compliant=False,
        total_fields=8,
        compliant_fields=6,
        non_compliant_fields=2,
        summary="Violations found",
        declarations_json=json.dumps([]),
        dpi_used=300,
    )
    db_session.add_all([insp1, insp2])
    await db_session.commit()

    officer1_token = create_access_token(data={"sub": test_officer.username, "role": test_officer.role.value})
    officer1_headers = {"Authorization": f"Bearer {officer1_token}"}

    admin_token = create_access_token(data={"sub": test_admin.username, "role": test_admin.role.value})
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Unauthenticated request -> 401
    res_unauth = await client.get("/api/v1/dashboard/officer-activity")
    assert res_unauth.status_code == 401

    # 2. Officer request -> SCOPED to self ONLY
    res_officer = await client.get("/api/v1/dashboard/officer-activity", headers=officer1_headers)
    assert res_officer.status_code == 200
    officers_list = res_officer.json()["officers"]
    usernames = [o["username"] for o in officers_list]
    assert test_officer.username in usernames
    assert officer2.username not in usernames, "Data leak: Officer must NOT see other officers' stats"
    assert len(officers_list) == 1

    # 3. Admin request -> Sees department-wide list
    res_admin = await client.get("/api/v1/dashboard/officer-activity", headers=admin_headers)
    assert res_admin.status_code == 200
    admin_officers_list = res_admin.json()["officers"]
    admin_usernames = [o["username"] for o in admin_officers_list]
    assert test_officer.username in admin_usernames
    assert officer2.username in admin_usernames
    assert len(admin_officers_list) >= 2


@pytest.mark.asyncio
async def test_dashboard_web_html_endpoint(
    client: AsyncClient, test_admin: User
):
    """
    Verify the /dashboard HTML server-side authentication gating:
    - Unauthenticated requests receive the standalone Login Gateway (login.html) with NO dashboard DOM.
    - Authenticated requests receive the full Control Room dashboard (index.html).
    """
    # 1. Unauthenticated request: served Login Gateway, zero metrics/DOM exposed
    res_unauth = await client.get("/dashboard")
    assert res_unauth.status_code == 200
    assert "text/html" in res_unauth.headers["content-type"]
    assert "Portal Gateway" in res_unauth.text
    assert "portal-login-form" in res_unauth.text
    assert "kpi-grid" not in res_unauth.text
    assert "trend-chart" not in res_unauth.text

    # 2. Authenticated request: served full Control Room DOM
    admin_token = create_access_token(data={"sub": test_admin.username, "role": test_admin.role.value})
    res_auth = await client.get("/dashboard", headers={"Authorization": f"Bearer {admin_token}"})
    assert res_auth.status_code == 200
    assert "text/html" in res_auth.headers["content-type"]
    assert "Enforcement Control Room" in res_auth.text
    assert "kpi-grid" in res_auth.text
    assert "trend-chart" in res_auth.text


@pytest.mark.asyncio
async def test_pre_capture_and_multi_panel_endpoints(
    client: AsyncClient, test_officer: User
):
    """
    Verify /scan/pre-capture and /scan/multi-panel endpoints with RBAC negative tests.
    """
    officer_token = create_access_token(data={"sub": test_officer.username, "role": test_officer.role.value})
    officer_headers = {"Authorization": f"Bearer {officer_token}"}

    # 1. Negative test: Unauthenticated pre-capture call -> 401
    res_unauth = await client.post("/api/v1/scan/pre-capture")
    assert res_unauth.status_code in [401, 403]

    # 2. Authenticated pre-capture call -> 200 with quality gate metrics
    # Simple 100x100 PNG
    import cv2
    import numpy as np
    blank = np.full((100, 100, 3), 200, dtype=np.uint8)
    _, buf = cv2.imencode(".png", blank)
    files = {"image": ("test.png", buf.tobytes(), "image/png")}
    res_pre = await client.post("/api/v1/scan/pre-capture", files=files, headers=officer_headers)
    assert res_pre.status_code == 200
    pre_body = res_pre.json()
    assert "status_code" in pre_body
    assert "laplacian_variance" in pre_body

    # 3. Negative test: Unauthenticated multi-panel call -> 401
    res_multi_unauth = await client.post("/api/v1/scan/multi-panel")
    assert res_multi_unauth.status_code in [401, 403]

    # 4. Negative test: Multi-panel with only 1 image -> 400
    files_single = [("images", ("test1.png", buf.tobytes(), "image/png"))]
    res_single = await client.post("/api/v1/scan/multi-panel", files=files_single, headers=officer_headers)
    assert res_single.status_code == 400
    assert "At least 2 panel images are required" in res_single.json()["detail"]


@pytest.mark.asyncio
async def test_product_scan_combines_clean_and_marker_photos(
    client: AsyncClient, test_officer: User, monkeypatch
):
    """POST /scan/product: text from a clean photo, scale from a marker photo, every photo hashed and stored."""
    import cv2
    import numpy as np
    from app.routers import scan as scan_router
    from app.schemas.scan import OCRResult, BoundingBox
    from app.services.calibration import CalibrationResult

    def png(shade):
        return cv2.imencode(".png", np.full((120, 120, 3), shade, dtype=np.uint8))[1].tobytes()

    clean_bytes, marker_bytes = png(200), png(210)

    def box(i):
        return BoundingBox(top_left=[20, 20 + 40 * i], top_right=[170, 20 + 40 * i],
                           bottom_right=[170, 50 + 40 * i], bottom_left=[20, 50 + 40 * i])

    def ocr(texts):
        return [OCRResult(text=t, confidence=0.95, font_height_px=30.0, bbox=box(i)) for i, t in enumerate(texts)]

    # The server re-encodes each upload once before calibration and OCR, so the fakes recognise a
    # photo by its pixels (grey level 200 = clean, 210 = marker), not by the uploaded bytes.
    def shade(data):
        return int(round(cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR).mean()))

    ocr_by_shade = {
        # Clean photo: MRP readable. Marker photo: the marker covers the MRP, net quantity is visible.
        200: ocr(["MRP Rs. 10.00 (Incl. of all taxes)", "Spice blend", "Keep cool", "Packed in India", "Batch 12"]),
        210: ocr(["Net Weight: 12 g", "Spice blend", "Keep cool", "Packed in India", "Batch 12"]),
    }

    def fake_calibrate(data):
        if shade(data) == 210:
            return CalibrationResult(calibration_method="aruco_40mm", reference_size_mm=40.0, pixels_per_mm=10.0,
                                     calibration_confidence=1.0, calibration_status="calibrated")
        return CalibrationResult(calibration_method="none", pixels_per_mm=None, calibration_status="no_reference")

    monkeypatch.setattr(scan_router, "calibrate_image", fake_calibrate)
    monkeypatch.setattr(scan_router, "preprocess_image", lambda data: data)
    monkeypatch.setattr(scan_router, "extract_text", lambda data, dpi, languages: ocr_by_shade[shade(data)])

    token = create_access_token(data={"sub": test_officer.username, "role": test_officer.role.value})
    headers = {"Authorization": f"Bearer {token}"}
    files = [
        ("images", ("clean.png", clean_bytes, "image/png")),
        ("images", ("marker.png", marker_bytes, "image/png")),
    ]

    # Negative: no token -> 401
    unauth = await client.post("/api/v1/scan/product", files=files)
    assert unauth.status_code == 401

    res = await client.post(
        "/api/v1/scan/product",
        files=files,
        headers=headers,
        data={"pdp_area_cm2": "60", "product_name": "  Everest Shahi Paneer Masala 12g  "},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["product_name"] == "Everest Shahi Paneer Masala 12g"

    # The officer-entered name is what lists and exports show
    listing = await client.get("/api/v1/inspections/", headers=headers)
    assert listing.json()[0]["product_name"] == "Everest Shahi Paneer Masala 12g"

    photos = body["photos"]
    assert [p["filename"] for p in photos] == ["clean.png", "marker.png"]
    assert photos[0]["image_hash_sha256"] == hashlib.sha256(clean_bytes).hexdigest()
    assert photos[1]["image_hash_sha256"] == hashlib.sha256(marker_bytes).hexdigest()
    assert [p["calibration_method"] for p in photos] == ["none", "aruco_40mm"]

    decls = {d["field_name"]: d for d in body["declarations"]}
    # MRP only readable in the clean photo: present, but its font size goes to review
    assert decls["mrp"]["detected"] is True
    assert decls["mrp"]["font_height_mm"] is None
    assert decls["mrp"]["font_review_required"] is True
    # Net quantity seen in the marker photo: measured (30 px / 10 px/mm = 3.0 mm) against the 60 cm2 PDP minimum
    assert decls["net_quantity"]["font_height_mm"] == 3.0
    assert decls["net_quantity"]["required_font_height_mm"] == 1.5

    # Stored once, with every photo's evidence hash
    detail = await client.get(f"/api/v1/inspections/{body['scan_id']}", headers=headers)
    assert detail.status_code == 200
    stored = detail.json()["photos"]
    assert [p["image_hash_sha256"] for p in stored] == [p["image_hash_sha256"] for p in photos]
    assert detail.json()["product_name"] == "Everest Shahi Paneer Masala 12g"

    # Both notices list every photo's hash
    import io
    from docx import Document
    from pypdf import PdfReader

    pdf = await client.get(f"/api/v1/inspections/{body['scan_id']}/notice.pdf", headers=headers)
    assert pdf.status_code == 200
    pdf_text = "".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf.content)).pages).replace("\n", "")
    docx = await client.get(f"/api/v1/inspections/{body['scan_id']}/notice.docx", headers=headers)
    assert docx.status_code == 200
    docx_text = " ".join(cell.text for t in Document(io.BytesIO(docx.content)).tables for row in t.rows for cell in row.cells)
    for p in photos:
        assert p["image_hash_sha256"] in pdf_text
        assert p["image_hash_sha256"] in docx_text
    assert "Everest Shahi Paneer Masala 12g" in pdf_text
    assert "Everest Shahi Paneer Masala 12g" in docx_text


def _phone_photo_with_marker(width=4000, height=3000, marker_px=800):
    """A phone-sized JPEG with a real 40 mm ArUco marker (DICT_4X4_50, id 0) drawn marker_px wide."""
    import cv2
    import numpy as np

    canvas = np.full((height, width, 3), 235, dtype=np.uint8)
    marker = cv2.aruco.generateImageMarker(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50), 0, marker_px)
    canvas[400:400 + marker_px, 600:600 + marker_px] = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)
    return cv2.imencode(".jpg", canvas, [cv2.IMWRITE_JPEG_QUALITY, 92])[1].tobytes()


@pytest.mark.asyncio
async def test_product_scan_measures_scale_and_text_on_the_same_image(
    client: AsyncClient, test_officer: User, monkeypatch
):
    """A full-size phone photo (4000x3000): the marker scale (px/mm) and the OCR boxes must refer to
    the same pixels, or every letter height in mm is wrong. The evidence hash stays on the raw upload."""
    import cv2
    import numpy as np
    from app.routers import scan as scan_router

    photo = _phone_photo_with_marker()
    seen = {}

    def recording_ocr(image, dpi, languages):
        seen["ocr_shape"] = image.shape[:2]
        return []

    real_calibrate = scan_router.calibrate_image

    def recording_calibrate(data):
        seen["calibration_shape"] = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR).shape[:2]
        return real_calibrate(data)

    monkeypatch.setattr(scan_router, "extract_text", recording_ocr)
    monkeypatch.setattr(scan_router, "calibrate_image", recording_calibrate)

    token = create_access_token(data={"sub": test_officer.username, "role": test_officer.role.value})
    res = await client.post(
        "/api/v1/scan/product",
        files=[("images", ("IMG_full.jpg", photo, "image/jpeg"))],
        headers={"Authorization": f"Bearer {token}"},
        data={"product_name": "Marker test"},
    )
    assert res.status_code == 200, res.text
    body = res.json()

    assert seen["calibration_shape"] == seen["ocr_shape"]
    assert max(seen["ocr_shape"]) <= 2048
    # The 800 px marker shrinks by 2048/4000, so the scale is 800 * 0.512 / 40 = 10.24 px per mm on the OCR image.
    assert body["photos"][0]["pixels_per_mm"] == pytest.approx(10.24, rel=0.03)
    assert body["photos"][0]["image_hash_sha256"] == hashlib.sha256(photo).hexdigest()


def _noisy_jpeg(width, height, seed):
    """A photo-like JPEG whose size is close to a real phone photo (noise does not compress)."""
    import cv2
    import numpy as np

    rng = np.random.default_rng(seed)
    pixels = rng.integers(0, 256, (height, width, 3), dtype=np.uint8)
    return cv2.imencode(".jpg", pixels, [cv2.IMWRITE_JPEG_QUALITY, 90])[1].tobytes()


@pytest.mark.asyncio
async def test_product_scan_accepts_several_full_size_photos(
    client: AsyncClient, test_officer: User, monkeypatch
):
    """The app now sends original phone photos (about 4 MB each). Three of them together are over
    10 MB; the request must still be accepted, because the 10 MB limit is per photo."""
    from app.routers import scan as scan_router

    monkeypatch.setattr(scan_router, "extract_text", lambda image, dpi, languages: [])
    photos = [_noisy_jpeg(2400, 1800, seed) for seed in range(3)]
    assert all(len(p) < 10 * 1024 * 1024 for p in photos)
    assert sum(len(p) for p in photos) > 10 * 1024 * 1024

    token = create_access_token(data={"sub": test_officer.username, "role": test_officer.role.value})
    res = await client.post(
        "/api/v1/scan/product",
        files=[("images", (f"IMG_{i}.jpg", p, "image/jpeg")) for i, p in enumerate(photos)],
        headers={"Authorization": f"Bearer {token}"},
        data={"product_name": "Size test"},
    )
    assert res.status_code == 200, res.text


@pytest.mark.asyncio
async def test_product_scan_still_rejects_one_photo_over_the_limit(client: AsyncClient, test_officer: User):
    """The per-photo limit is unchanged: a single photo over 10 MB is refused with its name."""
    big = _noisy_jpeg(4200, 3200, 7)
    assert len(big) > 10 * 1024 * 1024
    token = create_access_token(data={"sub": test_officer.username, "role": test_officer.role.value})
    res = await client.post(
        "/api/v1/scan/product",
        files=[("images", ("IMG_big.jpg", big, "image/jpeg"))],
        headers={"Authorization": f"Bearer {token}"},
        data={"product_name": "Size test"},
    )
    assert res.status_code == 413
    assert "IMG_big.jpg" in res.json()["detail"]


@pytest.mark.asyncio
async def test_single_scan_measures_scale_and_text_on_the_same_image(
    client: AsyncClient, test_officer: User, monkeypatch
):
    """POST /scan/ follows the same rule as /scan/product for a full-size photo."""
    import cv2
    import numpy as np
    from app.routers import scan as scan_router

    photo = _phone_photo_with_marker()
    seen = {}
    real_calibrate = scan_router.calibrate_image

    def recording_calibrate(data):
        seen["calibration_shape"] = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR).shape[:2]
        return real_calibrate(data)

    def recording_ocr(image, dpi, languages):
        seen["ocr_shape"] = image.shape[:2]
        return []

    monkeypatch.setattr(scan_router, "extract_text", recording_ocr)
    monkeypatch.setattr(scan_router, "calibrate_image", recording_calibrate)

    token = create_access_token(data={"sub": test_officer.username, "role": test_officer.role.value})
    res = await client.post(
        "/api/v1/scan/",
        files={"image": ("IMG_full.jpg", photo, "image/jpeg")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200, res.text
    assert seen["calibration_shape"] == seen["ocr_shape"]
    assert res.json()["image_hash_sha256"] == hashlib.sha256(photo).hexdigest()


@pytest.mark.asyncio
async def test_scan_endpoint_uses_pdp_area_form_field(
    client: AsyncClient, test_officer: User, monkeypatch
):
    """POST /scan/ with pdp_area_cm2 applies the Rule 7(2) area table; a non-positive area is rejected."""
    import cv2
    import numpy as np
    from app.routers import scan as scan_router
    from app.schemas.scan import OCRResult, BoundingBox
    from app.services.calibration import CalibrationResult

    def fake_calibrate(_bytes):
        return CalibrationResult(
            calibration_method="aruco_40mm", reference_size_mm=40.0,
            pixels_per_mm=10.0, calibration_confidence=1.0, calibration_status="calibrated",
        )

    def fake_ocr(_img, dpi, languages):
        texts = ["MRP Rs. 50.00 (Incl. of all taxes)", "Net Weight: 200 g", "Tasty", "Crunchy", "Fresh", "Golden"]
        return [
            OCRResult(
                text=t, confidence=0.95, font_height_px=50.0,
                bbox=BoundingBox(top_left=[20, 20 + 40 * i], top_right=[170, 20 + 40 * i],
                                 bottom_right=[170, 50 + 40 * i], bottom_left=[20, 50 + 40 * i]),
            )
            for i, t in enumerate(texts)
        ]

    monkeypatch.setattr(scan_router, "calibrate_image", fake_calibrate)
    monkeypatch.setattr(scan_router, "extract_text", fake_ocr)

    token = create_access_token(data={"sub": test_officer.username, "role": test_officer.role.value})
    headers = {"Authorization": f"Bearer {token}"}
    _, buf = cv2.imencode(".png", np.full((200, 200, 3), 230, dtype=np.uint8))

    res = await client.post(
        "/api/v1/scan/", headers=headers,
        files={"image": ("label.png", buf.tobytes(), "image/png")},
        data={"pdp_area_cm2": "300"},
    )
    assert res.status_code == 200, res.text
    mrp = next(d for d in res.json()["declarations"] if d["field_name"] == "mrp")
    assert mrp["pdp_area_cm2"] == 300.0
    assert mrp["required_font_height_mm"] == 2.5

    res_bad = await client.post(
        "/api/v1/scan/", headers=headers,
        files={"image": ("label.png", buf.tobytes(), "image/png")},
        data={"pdp_area_cm2": "0"},
    )
    assert res_bad.status_code == 422


