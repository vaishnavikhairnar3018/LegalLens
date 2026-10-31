"""
LenseScan Backend — FastAPI Application Entry Point.
Initializes the app, middleware, and routes.
"""

import logging
from contextlib import asynccontextmanager

from typing import Optional
from pathlib import Path
from fastapi import FastAPI, Request, status, Cookie, Header, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import init_db, get_db, get_session_factory
from app.routers import auth, scan, inspections, dashboard, ml_benchmark
from app.models.user import User, UserRole
from app.core.security import get_password_hash, decode_token

settings = get_settings()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("lensescan")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan events.
    - Startup: Initialize DB tables, pre-load OCR model, seed admin.
    - Shutdown: Cleanup resources.
    """
    # ── Startup ──
    logger.info("=" * 60)
    logger.info("LenseScan Backend Starting...")
    logger.info("=" * 60)

    # Initialize database tables
    logger.info("Initializing database tables...")
    await init_db()
    logger.info("Database tables ready.")

    # Seed default admin user if no users exist
    await _seed_admin_user()

    # Pre-load EasyOCR model (avoids cold-start latency on first request)
    logger.info("Pre-loading OCR engine (this may take a minute on first run)...")
    try:
        from app.services.ocr_pipeline import initialize_ocr
        initialize_ocr(settings.ocr_languages_list)
    except Exception as e:
        logger.warning(f"OCR pre-load deferred: {e}")

    logger.info("=" * 60)
    logger.info("LenseScan Backend Ready!")
    logger.info("=" * 60)

    yield

    # ── Shutdown ──
    logger.info("LenseScan Backend shutting down...")


# ── Create FastAPI App ──
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Secure Legal Metrology Compliance Checking System.\n\n"
        "Scans packaged commodity labels and validates compliance against "
        "India's Legal Metrology (Packaged Commodities) Rules, 2011.\n\n"
        "**Ministry of Consumer Affairs, Food & Public Distribution**"
    ),
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)


# ── Middleware ──

# CORS — Allow all origins (localhost on any port, Android emulator, local network)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_origin_regex=r"^https?://.*$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    """
    Middleware to enforce maximum request body size.
    Prevents DoS via oversized uploads.
    """
    # A product scan carries up to 8 photos, so the whole request may exceed the per-photo limit;
    # each photo is still checked against MAX_UPLOAD_SIZE_MB in the scan router.
    content_length = request.headers.get("content-length")
    if content_length:
        if int(content_length) > settings.max_request_size_bytes:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={
                    "detail": f"Request body too large. "
                    f"Maximum: {settings.max_request_size_bytes // (1024 * 1024)}MB"
                },
            )
    return await call_next(request)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains"
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return response


# ── Routers ──
app.include_router(auth.router, prefix="/api/v1")
app.include_router(scan.router, prefix="/api/v1")
app.include_router(inspections.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(ml_benchmark.router, prefix="/api/v1")

# ── Static Files & Web Dashboard ──
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


async def _verify_dashboard_token(token_str: Optional[str], db: AsyncSession) -> Optional[User]:
    """Helper to validate JWT token for dashboard server-side auth gate."""
    if not token_str:
        return None
    try:
        if token_str.startswith("Bearer "):
            token_str = token_str[7:]
        payload = decode_token(token_str)
        username = payload.get("sub")
        if not username:
            return None
        result = await db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()
        if user and user.is_active:
            return user
    except Exception:
        return None
    return None


@app.get("/dashboard", response_class=HTMLResponse, tags=["Web Dashboard"])
async def serve_dashboard(
    access_token: Optional[str] = Cookie(None),
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Serve the Enforcement Control Room web dashboard with server-side authentication:
    - If authenticated (valid session cookie, Bearer header, or token query param):
      Serves the full Control Room dashboard HTML.
    - If unauthenticated (no session / expired credentials):
      Serves ONLY the isolated Portal Gateway Login page. Zero dashboard DOM or data exposed.
    """
    auth_token = access_token or authorization or token
    user = await _verify_dashboard_token(auth_token, db)

    if not user:
        login_path = STATIC_DIR / "dashboard" / "login.html"
        if login_path.exists():
            return HTMLResponse(login_path.read_text(encoding="utf-8"), status_code=200)
        return HTMLResponse("<h1>Authentication Required</h1>", status_code=401)

    html_path = STATIC_DIR / "dashboard" / "index.html"
    if not html_path.exists():
        return HTMLResponse("<h1>Dashboard not found</h1>", status_code=404)
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


# ── Root & ML Accuracy Landing Page ──
@app.get("/", response_class=HTMLResponse, tags=["Web Dashboard"])
async def root_portal():
    """
    Landing portal serving the interactive Machine Learning Model Accuracy Dashboard
    and LMPC 2011 compliance architecture for viva and evaluation.
    """
    ml_html = Path(__file__).resolve().parent.parent.parent / "docs" / "ml_model_accuracy_dashboard.html"
    if ml_html.exists():
        return HTMLResponse(ml_html.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>LegalLens AI Backend Active</h1>")


@app.get("/ml", response_class=HTMLResponse, tags=["Web Dashboard"])
async def ml_landing_portal():
    """Direct route for interactive ML benchmarks and algorithm comparison graphs."""
    ml_html = Path(__file__).resolve().parent.parent.parent / "docs" / "ml_model_accuracy_dashboard.html"
    if ml_html.exists():
        return HTMLResponse(ml_html.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>ML Dashboard not found</h1>", status_code=404)


# ── Health Check ──
@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint for load balancers and monitoring."""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


# ── Helpers ──
async def _seed_admin_user():
    """Create or update default system accounts (admin, officer_verma, supervisor_sharma)."""
    from sqlalchemy import select

    factory = get_session_factory()
    async with factory() as session:
        accounts = [
            ("admin", "System Administrator", "Admin@123456", UserRole.ADMIN),
            ("officer_verma", "Rajesh Verma, Legal Metrology Officer", "officer123", UserRole.OFFICER),
            ("supervisor_sharma", "Pooja Sharma, Metrology Supervisor", "super123", UserRole.SUPERVISOR),
        ]
        for username, full_name, password, role in accounts:
            result = await session.execute(select(User).where(User.username == username))
            user = result.scalar_one_or_none()
            if not user:
                user = User(
                    username=username,
                    full_name=full_name,
                    hashed_password=get_password_hash(password),
                    role=role,
                    is_active=True,
                )
                session.add(user)
                logger.info(f"Seeded default account: {username}")
            else:
                user.hashed_password = get_password_hash(password)
                user.role = role
                user.is_active = True
        await session.commit()
        logger.info(
            "Default accounts ready: admin (Admin@123456), officer_verma (officer123), supervisor_sharma (super123)"
        )
