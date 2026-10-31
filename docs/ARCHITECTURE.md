# LenseScan — Technical Architecture Document

**System:** Legal Metrology Compliance Checking System  
**Problem Statement:** SIH 26034  
**Ministry:** Consumer Affairs, Food & Public Distribution  
**Version:** 2.0  
**Date:** September 2026

---

## 1. System Overview

LenseScan is a high-security software system that scans packaged commodity labels and checks compliance against India's **Legal Metrology (Packaged Commodities) Rules, 2011**. The system provides:

- AI-powered OCR label scanning with real-time compliance validation
- Statutory PDF & DOCX notice generation (Form LM-N1 / Form LM-C1)
- Cryptographic SHA-256 evidence chain-of-custody for court admissibility
- Role-based enforcement dashboard with aggregate analytics
- Mobile and web interfaces for field officers and supervisors

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    CLIENT LAYER                              │
│  ┌──────────────────┐  ┌──────────────────────────────────┐ │
│  │  Flutter Mobile   │  │  Web Dashboard (HTML/JS/CSS)    │ │
│  │  (iOS / Android)  │  │  (Chart.js, Vanilla JS)         │ │
│  │  Officer Field App │  │  Supervisor/Admin Control Room  │ │
│  └────────┬─────────┘  └──────────────┬───────────────────┘ │
│           │      HTTPS / JWT Bearer    │                     │
└───────────┼────────────────────────────┼─────────────────────┘
            │                            │
            ▼                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    API GATEWAY                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  FastAPI (Python 3.12, Uvicorn ASGI)                 │   │
│  │  ├─ /api/v1/auth/*       (JWT Authentication)        │   │
│  │  ├─ /api/v1/scan/*       (Label Upload + OCR)        │   │
│  │  ├─ /api/v1/inspections/*(Audit Trail + Reports)     │   │
│  │  ├─ /api/v1/dashboard/*  (Analytics Aggregation)     │   │
│  │  └─ /dashboard           (Web Dashboard Serving)     │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌─────────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ CORS Middleware  │  │ Size Limiter │  │ Security Hdrs │  │
│  └─────────────────┘  └──────────────┘  └───────────────┘  │
└─────────────────────────────────────────────────────────────┘
            │                            │
            ▼                            ▼
┌──────────────────────┐  ┌──────────────────────────────────┐
│   OCR + ML ENGINE    │  │      COMPLIANCE ENGINE            │
│  ┌────────────────┐  │  │  ┌────────────────────────────┐  │
│  │  EasyOCR 1.7   │  │  │  │  Rule Engine (JSON-based)  │  │
│  │  (en + hi)     │  │  │  │  LMPC Rules 2011           │  │
│  │  CPU Mode      │  │  │  │  ├─ Presence Check         │  │
│  └────────────────┘  │  │  │  ├─ Format Validation      │  │
│  ┌────────────────┐  │  │  │  ├─ Font Size (Sched. II)  │  │
│  │  OpenCV        │  │  │  │  ├─ Placement (Rule 8 PDP) │  │
│  │  CLAHE + DPI   │  │  │  │  └─ Special Rules          │  │
│  │  Preprocessing │  │  │  └────────────────────────────┘  │
│  └────────────────┘  │  │  ┌────────────────────────────┐  │
│  ┌────────────────┐  │  │  │  Declaration Classifier    │  │
│  │  SHA-256 Hash  │  │  │  │  (Regex + NLP Patterns)    │  │
│  │  (Evidence)    │  │  │  └────────────────────────────┘  │
│  └────────────────┘  │  └──────────────────────────────────┘
└──────────────────────┘
            │                            │
            ▼                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  PERSISTENCE LAYER                           │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  PostgreSQL (Encrypted at Rest)                       │   │
│  │  ├─ users            (Officers, Admins, Supervisors) │   │
│  │  └─ inspections      (Audit Trail + Evidence Hashes) │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  SQLAlchemy 2.0 (Async) + asyncpg                    │   │
│  │  Alembic (Schema Migrations)                          │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────┐
│                 REPORT GENERATION                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ ReportLab    │  │ python-docx  │  │ CSV/JSON Export  │  │
│  │ (PDF)        │  │ (DOCX)       │  │ (Batch Audit)    │  │
│  │ Form LM-N1   │  │ Editable     │  │                  │  │
│  │ Form LM-C1   │  │ Reports      │  │                  │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Data Model (ER Diagram)

```
┌──────────────────────────┐       ┌──────────────────────────────────┐
│         users            │       │          inspections              │
├──────────────────────────┤       ├──────────────────────────────────┤
│ id          INTEGER PK   │───┐   │ id               VARCHAR(36) PK  │
│ username    VARCHAR(150)  │   │   │ officer_id       INTEGER FK ─────┤
│ full_name   VARCHAR(255)  │   └──>│ image_filename   VARCHAR(255)    │
│ hashed_pwd  VARCHAR(255)  │       │ image_hash_sha256 VARCHAR(64)    │
│ role        ENUM(officer, │       │ overall_compliant BOOLEAN        │
│             admin,        │       │ total_fields      INTEGER        │
│             supervisor)   │       │ compliant_fields  INTEGER        │
│ is_active   BOOLEAN       │       │ non_compliant_flds INTEGER       │
│ created_at  TIMESTAMP     │       │ summary           TEXT           │
│ updated_at  TIMESTAMP     │       │ declarations_json  TEXT          │
└──────────────────────────┘       │ raw_ocr_json       TEXT          │
                                    │ dpi_used           INTEGER       │
                                    │ created_at         TIMESTAMP     │
                                    └──────────────────────────────────┘
```

---

## 4. Security Architecture

### 4.1 Authentication & Authorization
- **JWT Bearer Tokens** (HS256, 60-min expiry) via `python-jose`
- **bcrypt** password hashing (cost factor 12) via `passlib`
- **Role-Based Access Control (RBAC):**
  - `officer` — scan labels, view own inspections
  - `supervisor` — view all inspections, analytics dashboard
  - `admin` — all permissions + user registration

### 4.2 OWASP Mobile Top 10 Defenses
| Threat | Mitigation |
|--------|-----------|
| M1: Improper Credential Usage | JWT short-lived tokens, bcrypt hashing |
| M2: Inadequate Supply Chain | Zero-PaddleOCR compliance, dependency audit |
| M3: Insecure Auth | OAuth2 password flow, role enforcement |
| M4: Insufficient I/O Validation | Input sanitizer, SQL injection checks |
| M5: Insecure Communication | HTTPS enforcement, HSTS headers |
| M8: Security Misconfiguration | No debug in prod, strict CORS |

### 4.3 Data Sovereignty
- **STRICT CONSTRAINT:** No PaddleOCR or Chinese-origin frameworks used
- All OCR inference runs on-premise (EasyOCR CPU mode)
- No external API calls for data processing
- PostgreSQL encrypted at rest

### 4.4 Evidence Chain-of-Custody
- SHA-256 hash computed on raw uploaded bytes **before** any preprocessing
- Hash stored in DB and embedded in statutory PDF/DOCX notices
- Court-admissible under Section 36 of The Legal Metrology Act, 2009

---

## 5. Compliance Engine

### 5.1 LMPC Rules 2011 Coverage

Citations verified against the Ministry of Consumer Affairs consolidated text,
*Legal Metrology (Packaged Commodities) Rules, 2011 with all amendments*.

| Rule | Declaration | Checks Performed |
|------|------------|------------------|
| Rule 6(1)(a) | Manufacturer / Packer / Importer Name & Address | Presence, PIN code, address format |
| Rule 6(1)(aa) | Country of Origin (imported products) | Presence |
| Rule 6(1)(b) | Common / Generic Name | Presence |
| Rule 6(1)(c) | Net Quantity | Presence, format, unit validation |
| Rule 6(1)(d) | Month & Year of Manufacture | Presence, date format |
| Rule 6(1)(da) | Best Before / Use By | Presence, date format |
| Rule 6(1)(e) | MRP (inclusive of all taxes) | Presence, format, "incl. all taxes" |
| Rule 6(2) | Consumer Care | Presence, phone/email |
| Rule 6(11) | Unit Sale Price | Reconciliation with MRP / net quantity |
| Rule 7(2) | Font Height | Measured (ArUco/coin/card scale) vs. Table-I minimum for the officer-supplied PDP area, all declarations; no area or no marker → manual review |
| Rule 8(1) | Placement (PDP) | Declarations on the Principal Display Panel |
| Rule 12(6) | Quantity qualifiers | No "approximately", "minimum", "not less than" etc. |
| Rule 13(2), 13(5) | Units of quantity | g/ml below 1 kg/1 L; SI unit symbols |

Rule 5 and the Second Schedule (standard pack sizes) were omitted w.e.f. 01.10.2022
(GSR 779(E)); no pack-size check is performed. Conflicting MRPs on one package are
flagged for officer review without a statutory citation.

### 5.2 Placement Validation (Rule 8(1) PDP)
Using OCR bounding box coordinates, the engine performs:
1. **PDP Co-location Check:** MRP and Net Quantity must be within 40% proximity
2. **Margin Detection:** Key declarations must not be in extreme margins (≤5%)
3. **Scatter Analysis:** Key declarations must not be spread >70% of label diagonal

---

## 6. Technology Stack Summary

| Component | Technology | Version |
|-----------|-----------|---------|
| Backend API | FastAPI | 0.115+ |
| ASGI Server | Uvicorn | 0.30+ |
| Database | PostgreSQL + asyncpg | 16+ |
| ORM | SQLAlchemy (Async) | 2.0+ |
| OCR Engine | EasyOCR | 1.7+ |
| Image Processing | OpenCV (Headless) | 4.10+ |
| PDF Generation | ReportLab | 5.0+ |
| DOCX Generation | python-docx | 1.1+ |
| Authentication | python-jose, passlib | Latest |
| Mobile App | Flutter (Dart) | 3.x |
| Web Dashboard | Vanilla HTML/CSS/JS + Chart.js | 4.4+ |
| Migrations | Alembic | 1.13+ |
