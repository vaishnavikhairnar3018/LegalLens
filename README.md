<div align="center">

# ⚖️ LegalLens AI
### Automated Legal Metrology (LMPC Rules, 2011) Compliance & Enforcement Platform

[![SIH Problem Statement](https://img.shields.io/badge/SIH%202026-Problem%2026034-004D40?style=for-the-badge&logo=target)](https://www.sih.gov.in/)
[![Ministry](https://img.shields.io/badge/Ministry-Consumer%20Affairs%2C%20Food%20%26%20Public%20Distribution-134E4A?style=for-the-badge)](https://consumeraffairs.nic.in/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI%20%7C%20Python%203.12-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Flutter](https://img.shields.io/badge/Frontend-Flutter%203.x%20%7C%20Dart-02569B?style=for-the-badge&logo=flutter)](https://flutter.dev/)
[![OCR Engine](https://img.shields.io/badge/AI%2FOCR-EasyOCR%20%2B%20OpenCV-FF6F00?style=for-the-badge)](https://github.com/JaidedAI/EasyOCR)
[![Status](https://img.shields.io/badge/Build-Passing%20(27%2F27%20Tests)-2E7D32?style=for-the-badge)](https://pytest.org/)

<p align="center">
  <b>A state-of-the-art mobile and web compliance system empowering Legal Metrology Officers to verify packaged commodities, enforce statutory declarations, and generate Section 65B tamper-proof legal notices within seconds.</b>
</p>

[Live Demo](#-quick-hosting--live-demo-setup) • [Key Features](#-key-features) • [Architecture](#-system-architecture) • [Getting Started](#-getting-started) • [API Reference](#-api-specification) • [Presentation Credentials](#-demo-accounts)

---

</div>

## 📌 Executive Summary & Problem Context

* **Problem Statement:** SIH 26034
* **Beneficiary Organization:** Ministry of Consumer Affairs, Food & Public Distribution (Department of Legal Metrology, Government of India)
* **Governing Legislation:** Legal Metrology Act, 2009 & Legal Metrology (Packaged Commodities) Rules, 2011 (LMPC Rules)

Under Indian law, every pre-packaged commodity sold across physical retail or e-commerce must feature mandatory statutory declarations on its Principal Display Panel (PDP). Traditional inspections are:
1. **Manual & Labor Intensive:** Officers spend 15–20 minutes per product measuring fonts with physical calipers and cross-referencing statutory tables.
2. **Subjective:** Human verification of ambiguous date formats, combined unit sizes, and obscure font ratios leads to legal disputes.
3. **Chain-of-Custody Vulnerabilities:** Evidence gathered during raids is routinely challenged in court due to uncertified image capture without cryptographic provenance.

**LegalLens AI** automates this entire pipeline. With a single camera capture or multi-panel scan, the system detects physical scale using ArUco optical markers, extracts text in English and Hindi, evaluates 8 mandatory statutory rules against physical packaging dimensions, and generates legally compliant Form LM-N1 Violation Notices and Form LM-C1 Certificates.

---

## 🚀 Key Features

### 1. Multi-Panel Computer Vision & OCR Engine
- **Bilingual Extraction:** High-accuracy extraction in English and Hindi using EasyOCR 1.7 and OpenCV CLAHE contrast enhancement.
- **Pre-Capture Heuristics:** Real-time feedback for blur (Laplacian variance > 100.0) and glare detection before inspection submission.
- **Cross-Panel Consistency Service:** Stitches Principal Display Panel (PDP), Manufacturing Panels, and Back Panels to resolve split declarations (e.g., *"See back for MRP"*).

### 2. Optical Scale Recovery & Rule 7 Font Verification
- **ArUco Marker Calibration:** Metric optical scale recovery ($PPM$ - pixels per millimeter) enables measuring actual physical font height down to tenths of a millimeter.
- **Rule 7(2) Font Height:** The officer optionally enters the Principal Display Panel area; the minimum numeral/letter height comes from Rule 7(2) Table-I (GSR 629(E), w.e.f. 01.01.2018): A ≤ 50 cm² → 1.0 mm, ≤ 100 → 1.5 mm, ≤ 500 → 2.5 mm, ≤ 2500 → 4.0 mm, above → 6.0 mm. Applied to every Rule 6 declaration. Without a calibration marker or a PDP area, the result is a manual-review flag, never a violation.
- **Fail-Safe Placement Geometry:** Automatically identifies curved bottles or skewed packaging. When bounding-box geometry is ambiguous, it flags a *Human Review State* instead of generating false-positive notices.

### 3. Comprehensive LMPC 2011 Rule Checks
| Statutory Rule | Declaration Check | Enforced Standard |
| :--- | :--- | :--- |
| **Rule 6(1)(a)** | Manufacturer / Packer / Importer Name & Address | Complete postal address with Pin Code |
| **Rule 6(1)(aa)** | Country of Origin | Mandatory for imported products |
| **Rule 6(1)(b)** | Common / Generic Name | Common name on PDP |
| **Rule 6(1)(c)** | Net Quantity | Standard unit of weight, measure or number |
| **Rule 6(1)(d)** | Month & Year of Manufacture | Valid `MM/YYYY` or `Month YYYY` |
| **Rule 6(1)(da)** | Best Before / Use By | Required where the commodity may become unfit for consumption |
| **Rule 6(1)(e)** | Maximum Retail Price (MRP) | Format `MRP ₹ xx.xx (incl. of all taxes)` |
| **Rule 6(2)** | Consumer Care Details | Name, address, telephone, e-mail |

Related checks: Rule 6(11) unit sale price, Rule 7(2) font height, Rule 8(1) declarations on the PDP, Rule 12(6) prohibited quantity qualifiers, Rule 13 units. Citations are verified against the Ministry of Consumer Affairs consolidated text of the LMPC Rules 2011 with all amendments.

### 4. Cryptographic Evidence Chain-of-Custody
- **Section 65B Indian Evidence Act Admissibility:** SHA-256 cryptographic hashing executed on raw image bytes prior to any processing.
- **Tamper-Evident Audit Trail:** Every scan logged immutably with GPS coordinates, inspection timestamp, officer ID, and original file hash.
- **Instant Statutory Exports:** 1-click generation of PDF Legal Notices (Form LM-N1) and Certificates of Compliance (Form LM-C1), along with editable Word (`.docx`), CSV, and JSON audit logs.

### 5. Multi-Tiered User Architecture & Role-Based Access Control (RBAC)
- **Enforcement Officer:** Mobile field scanning, multi-panel capture, inspection history, instant notice dispatch.
- **Supervisor:** Zone-level analytics, officer activity audit, review triage.
- **Administrator:** System configuration, rule threshold adjustments, state-wide export logs.

---

## 🏛️ System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                          PRESENTATION LAYER                            │
│  ┌───────────────────────────────┐  ┌────────────────────────────────┐ │
│  │   Flutter Cross-Platform      │  │   Control Room Web Dashboard   │ │
│  │   • Android / iOS Field App   │  │   • Executive Analytics        │ │
│  │   • Flutter Web (PWA Ready)   │  │   • Chart.js Compliance Trends │ │
│  │   • Live Viewfinder + Scale   │  │   • Inspection Export Hub      │ │
│  └───────────────┬───────────────┘  └───────────────┬────────────────┘ │
└──────────────────┼──────────────────────────────────┼──────────────────┘
                   │         HTTPS / JWT Auth         │
                   ▼                                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        APPLICATION API GATEWAY                         │
│  FastAPI (Python 3.12 ASGI)                                            │
│  ├─ /api/v1/auth/login            (Role-based JWT Token Generation)   │
│  ├─ /api/v1/scan/upload           (Multi-panel Image + ArUco Pipeline)│
│  ├─ /api/v1/inspections           (Officer-scoped Audit Trail)        │
│  ├─ /api/v1/inspections/{id}/pdf  (Form LM-N1 / LM-C1 Legal Notices)  │
│  └─ /api/v1/dashboard/analytics   (Time-series Metrics & Rates)       │
└──────────────────┬──────────────────────────────────┬──────────────────┘
                   │                                  │
                   ▼                                  ▼
┌──────────────────────────────────────┐  ┌──────────────────────────────┐
│          COMPUTER VISION             │  │        RULE ENGINE           │
│  ┌────────────────────────────────┐  │  │  ┌────────────────────────┐  │
│  │ EasyOCR 1.7 (English + Hindi)  │  │  │  │ 8 LMPC 2011 Rules Engine│  │
│  │ CLAHE Preprocessing            │  │  │  │ Rule 7 Font Math       │  │
│  │ ArUco Optical Scale Recovery   │  │  │  │ Proximity & PDP Ratio  │  │
│  │ Raw Byte SHA-256 Hashing       │  │  │  │ Human Review Fallback  │  │
│  └────────────────────────────────┘  │  │  └────────────────────────┘  │
└──────────────────┬───────────────────┘  └──────────────┬───────────────┘
                   │                                     │
                   ▼                                     ▼
┌────────────────────────────────────────────────────────────────────────┐
│                         PERSISTENCE & EXPORTS                          │
│  • SQLite (Local Zero-Config) / PostgreSQL 16 (Enterprise Production)   ││  • ReportLab Engine (Tamper-evident Form LM-N1 Legal Notices)          │
│  • python-docx Generator (Standard Court-Ready Case Filings)           │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 📦 Real-World Dataset & Test Products

The platform comes pre-seeded with 93 high-resolution labeled products across diverse fast-moving consumer goods (FMCG):

```
product/
├── 01_balaji_gathiya_front_missing_mrp.jpg          [Violation: Rule 6(1)(e)]
├── 10_ram_bandhu_chakali_back_font_violation.jpg    [Violation: Rule 7(2) Font Height]
├── 11_maggi_pichkoo_sauce_front_compliant.jpg       [Compliant: All 8 Fields Valid]
├── 21_ponds_talc_curved_review.jpg                  [Review: Curved Surface Geometry]
├── 23_dark_fantasy_bourbon_box_placement.jpg        [Review: Ambiguous PDP Orientation]
├── 64_britannia_nutrichoice_front_pdp.jpg           [Compliant: All 8 Fields Valid]
├── 81_surf_excel_stain_eraser_front_pdp.jpg         [Compliant: All 8 Fields Valid]
└── 86_vim_lemon_dishwash_bar_front.jpg              [Compliant: All 8 Fields Valid]
```

---



---

## 🔑 Demo Accounts

Use these accounts to demonstrate different roles during presentations or evaluations:

| Role | Username | Password | Access Capabilities |
| :--- | :--- | :--- | :--- |
| **Field Enforcement Officer** | `officer_verma` | `officer123` | Mobile scanning, field inspections, notice downloads *(1-Tap Biometric button on login)* |
| **Enforcement Supervisor** | `supervisor_sharma`| `super123` | Control room dashboard, audit logs, officer verification |
| **State Administrator** | `admin_sharma` | `admin123` | Full system configuration, bulk CSV/JSON audit exports |

---

## 📋 API Specification

### Authentication
- `POST /api/v1/auth/login` — Authenticate and receive signed JWT Bearer token.
- `GET /api/v1/auth/me` — Retrieve active officer profile and role permissions.

### Inspection & Scanning
- `POST /api/v1/scan/upload` — Upload product label image with optional ArUco marker.
- `GET /api/v1/inspections` — Fetch history of inspections (scoped to officer role).
- `GET /api/v1/inspections/{id}` — Full compliance breakdown, OCR bounding boxes, and statutory citations.

### Statutory Exports
- `GET /api/v1/inspections/{id}/pdf` — Generate Form LM-N1 (Legal Notice) or Form LM-C1 (Certificate).
- `GET /api/v1/inspections/{id}/docx` — Download editable Microsoft Word inspection notice.
- `GET /api/v1/inspections/export/csv` — Batch export inspection records for court filings.

### Enforcement Control Room
- `GET /api/v1/dashboard/analytics` — Real-time compliance rate, total scans, and violation frequency.
- `GET /dashboard` — Web-based monitoring console for supervisors and ministry officials.

---

## 👥 Project Information & Authors

* **Team:** NextGenCodeX
* **Application Title:** LegalLens AI 
* **Governing Body:** Ministry of Consumer Affairs, Food & Public Distribution
* **Statutory Compliance:** Legal Metrology (Packaged Commodities) Rules, 2011 & Indian Evidence Act, Section 65B
* **License:** [MIT License](LICENSE)

---

<div align="center">
  <sub>Developed for Smart India Hackathon 2026 • Legal Metrology Enforcement Division</sub>
</div>
