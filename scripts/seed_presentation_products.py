"""
Seed LenseScan database with rich, authentic products from the dataset
specifically formatted for high-impact PPT presentation screenshots.

Features:
- Real FMCG brands (Nestle Maggi, Balaji, Britannia, ITC Dark Fantasy, Surf Excel, Vim, Godrej, Haldiram, etc.)
- Real statutory citations (Rule 6(1)(e), Rule 6(1)(a), Rule 7(2) font height, Rule 8(1) placement, etc.)
- Realistic timestamps distributed across TODAY, YESTERDAY, and THIS WEEK
- Full 8-field declaration lists for Results Screen & PDF/Word report generation
"""

import sys
import json
import uuid
import hashlib
import sqlite3
from datetime import datetime, timedelta, timezone

def generate_declarations(p):
    """Generate 8 statutory declaration records based on product metadata."""
    is_compliant = p["status"] == "COMPLIANT"
    status = p["status"]
    
    # 8 standard mandatory fields under LMPC 2011 Rule 6
    fields = [
        {
            "field_name": "mrp",
            "display_name": "Maximum Retail Price (MRP)",
            "rule": "Rule 6(1)(e)",
            "val": p.get("mrp", "₹15.00"),
            "font": 2.8,
            "req_font": 2.0,
            "is_violation": "Rule 6(1)(e)" in p.get("citation", ""),
        },
        {
            "field_name": "net_quantity",
            "display_name": "Net Quantity",
            "rule": "Rule 6(1)(c)",
            "val": p.get("net_qty", "100g"),
            "font": 3.2,
            "req_font": 2.5,
            "is_violation": "Rule 6(1)(c)" in p.get("citation", ""),
        },
        {
            "field_name": "manufacturer",
            "display_name": "Manufacturer Name & Address",
            "rule": "Rule 6(1)(a)",
            "val": p.get("mfg", "Manufactured & Packed in India"),
            "font": 2.1,
            "req_font": 2.0,
            "is_violation": "Rule 7(2)" in p.get("citation", "") and "manufacturer" in p.get("details", "").lower(),
        },
        {
            "field_name": "mfg_date",
            "display_name": "Month & Year of Manufacture",
            "rule": "Rule 6(1)(d)",
            "val": p.get("date", "06/2026"),
            "font": 2.4,
            "req_font": 1.5,
            "is_violation": "Rule 6(1)(d)" in p.get("citation", "") and "date" in p.get("details", "").lower(),
        },
        {
            "field_name": "expiry_date",
            "display_name": "Best Before / Expiry Period",
            "rule": "Rule 6(1)(da)",
            "val": "Best Before 12 Months from Packing",
            "font": 2.2,
            "req_font": 1.5,
            "is_violation": False,
        },
        {
            "field_name": "consumer_care",
            "display_name": "Consumer Care Helpline & Email",
            "rule": "Rule 6(2)",
            "val": "Toll Free: 1800-22-1234 | care@brand.in",
            "font": 2.0,
            "req_font": 1.5,
            "is_violation": "Rule 6(2)" in p.get("citation", "") and "consumer" in p.get("details", "").lower(),
        },
        {
            "field_name": "unit_sale_price",
            "display_name": "Unit Sale Price (USP)",
            "rule": "Rule 6(11)",
            "val": p.get("usp", "₹0.15/g"),
            "font": 2.4,
            "req_font": 1.5,
            "is_violation": False,
        },
        {
            "field_name": "country_of_origin",
            "display_name": "Country of Origin",
            "rule": "Rule 6(1)(aa)",
            "val": "Country of Origin: India",
            "font": 2.2,
            "req_font": 1.5,
            "is_violation": False,
        },
    ]

    is_placement_review = status == "REVIEW" and "Rule 8(1)" in p.get("citation", "")
    is_font_violation = "Rule 7(2)" in p.get("citation", "")

    decls = []
    for f in fields:
        field_viol = f["is_violation"] or (is_font_violation and f["field_name"] == "manufacturer")
        compliant = not field_viol and not is_placement_review

        violations = []
        if field_viol:
            violations.append(p.get("details", f"Mandatory declaration non-compliant under {f['rule']}"))

        font_val = 1.2 if field_viol and is_font_violation else f["font"]

        decls.append({
            "field_name": f["field_name"],
            "display_name": f["display_name"],
            "detected": not (field_viol and "missing" in p.get("details", "").lower()),
            "value": None if (field_viol and "missing" in p.get("details", "").lower()) else f["val"],
            "compliant": compliant,
            "violations": violations,
            "font_height_mm": font_val,
            "required_font_height_mm": f["req_font"],
            "confidence": 0.94 if compliant else 0.42,
            "placement_compliant": not is_placement_review,
            "placement_violations": [p.get("details", "Placement requires review")] if is_placement_review else [],
            "bbox_center": [450.0, 600.0],
            "placement_review_required": is_placement_review,
            "placement_review_reason": p.get("details") if is_placement_review else None,
            "coverage_review_required": False,
            "font_review_required": False,
        })
    return decls


def seed_database():
    conn = sqlite3.connect("lensescan.db")
    c = conn.cursor()

    now = datetime.now(timezone.utc)

    # 26 Curated Products directly from LenseScan Dataset
    products = [
        # ── TODAY (Most Recent 4 for Home Screen & Top of History) ──
        {
            "filename": "11_maggi_pichkoo_sauce_front_compliant.jpg",
            "brand": "Maggi",
            "product_name": "Pichkoo Rich Tomato Ketchup",
            "status": "COMPLIANT",
            "citation": "None",
            "details": "None (Fully compliant with all Rule 6 declarations)",
            "mrp": "₹15.00",
            "net_qty": "90g",
            "usp": "₹0.17/g",
            "date": "05/2026",
            "mfg": "Nestlé India Limited, Moga, Punjab PIN 142001",
            "offset_hours": 1.2,
        },
        {
            "filename": "01_balaji_gathiya_front_missing_mrp.jpg",
            "brand": "Balaji Wafers",
            "product_name": "Papdi Gathiya Namkeen",
            "status": "VIOLATION",
            "citation": "Rule 6(1)(e)",
            "details": "Missing MRP on front Principal Display Panel",
            "mrp": None,
            "net_qty": "24g",
            "usp": "₹0.21/g",
            "date": "06FEB26",
            "mfg": "Balaji Wafers Pvt. Ltd., Vajdi, Rajkot PIN 360021",
            "offset_hours": 2.5,
        },
        {
            "filename": "64_britannia_nutrichoice_front_pdp.jpg",
            "brand": "Britannia",
            "product_name": "NutriChoice Digestive Biscuit",
            "status": "COMPLIANT",
            "citation": "None",
            "details": "None (Fully compliant with all Rule 6 declarations)",
            "mrp": "₹30.00",
            "net_qty": "100g",
            "usp": "₹0.30/g",
            "date": "08/2026",
            "mfg": "Britannia Industries Ltd., Kolkata, West Bengal PIN 700017",
            "offset_hours": 3.8,
        },
        {
            "filename": "23_dark_fantasy_bourbon_box_placement_violation.jpg",
            "brand": "Sunfeast",
            "product_name": "Dark Fantasy Bourbon Cookies",
            "status": "REVIEW",
            "citation": "Rule 8(1)",
            "details": "Placement Review: Mandatory declarations fragmented across box folds",
            "mrp": "₹142.00",
            "net_qty": "450g",
            "usp": "₹0.32/g",
            "date": "04/08/26",
            "mfg": "ITC Limited, Virginia House, Kolkata PIN 700071",
            "offset_hours": 4.5,
        },

        # ── YESTERDAY (6 diverse items) ──
        {
            "filename": "81_surf_excel_stain_eraser_front_pdp.jpg",
            "brand": "Surf Excel",
            "product_name": "Stain Eraser Detergent Bar",
            "status": "COMPLIANT",
            "citation": "None",
            "details": "None (Fully compliant)",
            "mrp": "₹20.00",
            "net_qty": "200g",
            "usp": "₹0.10/g",
            "date": "06/2026",
            "mfg": "Hindustan Unilever Limited, Mumbai PIN 400099",
            "offset_hours": 26.0,
        },
        {
            "filename": "86_vim_lemon_dishwash_bar_front.jpg",
            "brand": "Vim",
            "product_name": "Lemon Dishwash Bar",
            "status": "COMPLIANT",
            "citation": "None",
            "details": "None (Fully compliant)",
            "mrp": "₹10.00",
            "net_qty": "135g",
            "usp": "₹0.07/g",
            "date": "07/2026",
            "mfg": "Hindustan Unilever Limited, Mumbai PIN 400099",
            "offset_hours": 28.5,
        },
        {
            "filename": "56_samrat_khaman_dhokla_front_pdp.jpg",
            "brand": "Samrat",
            "product_name": "Khaman Dhokla Instant Mix",
            "status": "VIOLATION",
            "citation": "Rule 6(1)(c)",
            "details": "Net Quantity omitted on Principal Display Panel",
            "mrp": "₹65.00",
            "net_qty": None,
            "usp": "₹0.33/g",
            "date": "09/2026",
            "mfg": "Parakh Agro Industries Ltd., Pune PIN 411001",
            "offset_hours": 31.0,
        },
        {
            "filename": "47_goodknight_flash_carton_front.jpg",
            "brand": "Godrej",
            "product_name": "GoodKnight Flash Repellent",
            "status": "COMPLIANT",
            "citation": "None",
            "details": "None (Fully compliant)",
            "mrp": "₹85.00",
            "net_qty": "45ml",
            "usp": "₹1.89/ml",
            "date": "08/2026",
            "mfg": "Godrej Consumer Products Ltd., Mumbai PIN 400079",
            "offset_hours": 34.0,
        },
        {
            "filename": "32_haldiram_rusky_toast_front_pdp.jpg",
            "brand": "Haldiram's",
            "product_name": "Rusky Atta Toast",
            "status": "COMPLIANT",
            "citation": "None",
            "details": "None (Fully compliant)",
            "mrp": "₹40.00",
            "net_qty": "150g",
            "usp": "₹0.27/g",
            "date": "2026",
            "mfg": "Haldiram Snacks Food Pvt. Ltd., Noida PIN 201307",
            "offset_hours": 37.0,
        },
        {
            "filename": "10_ram_bandhu_chakali_back_font_violation.jpg",
            "brand": "Ram Bandhu",
            "product_name": "Chakali Bhajani Mix",
            "status": "VIOLATION",
            "citation": "Rule 7(2)",
            "details": "Font height non-compliance under Rule 7(2) relative to PDP",
            "mrp": "₹55.00",
            "net_qty": "200g",
            "usp": "₹0.28/g",
            "date": "2026",
            "mfg": "Empire Spices and Foods Ltd., Nashik PIN 422007",
            "offset_hours": 40.0,
        },

        # ── THIS WEEK (16 items) ──
        {
            "filename": "21_ponds_talc_curved_review.jpg",
            "brand": "Pond's",
            "product_name": "Dreamflower Pink Lily Body Talc",
            "status": "REVIEW",
            "citation": "Rule 8(1)",
            "details": "Geometry Review: Curvature causes optical character distortion",
            "mrp": "₹140.00",
            "net_qty": "300g",
            "date": "24 months from mfg",
            "mfg": "Hindustan Unilever Limited, Mumbai PIN 400099",
            "offset_hours": 50.0,
        },
        {
            "filename": "17_chings_manchow_soup_missing_mfg_date.jpg",
            "brand": "Ching's Secret",
            "product_name": "Manchow Instant Soup",
            "status": "VIOLATION",
            "citation": "Rule 6(1)(d)",
            "details": "Date of manufacture/packing absent from front panel",
            "mrp": "₹15.00",
            "net_qty": "21g",
            "usp": "₹0.71/g",
            "date": None,
            "mfg": "Capital Foods Pvt. Ltd., Mumbai PIN 400072",
            "offset_hours": 62.0,
        },
        {
            "filename": "15_samrat_maida_flour_front_compliant.jpg",
            "brand": "Samrat",
            "product_name": "MP Maida Flour",
            "status": "COMPLIANT",
            "citation": "None",
            "details": "None (Fully compliant)",
            "mrp": "₹45.00",
            "net_qty": "500g",
            "usp": "₹0.09/g",
            "date": "07/2026",
            "mfg": "Parakh Agro Industries Ltd., Pune PIN 411001",
            "offset_hours": 74.0,
        },
        {
            "filename": "77_amin_persian_dates_front_pdp.jpg",
            "brand": "Amin",
            "product_name": "Persian Premium Dates",
            "status": "COMPLIANT",
            "citation": "None",
            "details": "None (Fully compliant)",
            "mrp": "₹180.00",
            "net_qty": "500g",
            "usp": "₹0.36/g",
            "date": "2026",
            "mfg": "Amin Trading Corp., Mumbai PIN 400009",
            "offset_hours": 86.0,
        },
        {
            "filename": "13_suruchi_soysauce_missing_mrp.jpg",
            "brand": "Suruchi",
            "product_name": "Dark Soy Sauce",
            "status": "VIOLATION",
            "citation": "Rule 6(1)(e)",
            "details": "Missing MRP in primary front panel area",
            "mrp": None,
            "net_qty": "100g",
            "date": "08/2026",
            "mfg": "Suruchi Spices Pvt. Ltd., Nagpur PIN 440008",
            "offset_hours": 98.0,
        },
        {
            "filename": "50_mysore_sandal_kleenol_front.jpg",
            "brand": "Karnataka Soaps",
            "product_name": "Mysore Sandal Kleenol Soap",
            "status": "COMPLIANT",
            "citation": "None",
            "details": "None (Fully compliant)",
            "mrp": "₹45.00",
            "net_qty": "125g",
            "usp": "₹0.36/g",
            "date": "06/2026",
            "mfg": "Karnataka Soaps and Detergents Ltd., Bangalore PIN 560055",
            "offset_hours": 110.0,
        },
        {
            "filename": "35_bishnoi_toast_netqty_batch.jpg",
            "brand": "Bishnoi Foods",
            "product_name": "Special Selection Atta Toast",
            "status": "COMPLIANT",
            "citation": "None",
            "details": "None (Fully compliant)",
            "mrp": "₹25.00",
            "net_qty": "150g",
            "usp": "₹0.17/g",
            "date": "2026",
            "mfg": "Bishnoi Foods, Palsana, Surat PIN 394305",
            "offset_hours": 120.0,
        },
        {
            "filename": "04_balaji_mungdal_back_compliant.jpg",
            "brand": "Balaji Wafers",
            "product_name": "Mung Dal Savouries",
            "status": "COMPLIANT",
            "citation": "None",
            "details": "None (Fully compliant)",
            "mrp": "₹5.00",
            "net_qty": "24g",
            "usp": "₹0.21/g",
            "date": "06FEB26",
            "mfg": "Balaji Wafers Pvt. Ltd., Rajkot PIN 360021",
            "offset_hours": 130.0,
        },
        {
            "filename": "07_balaji_sev_murmura_back_compliant.jpg",
            "brand": "Balaji Wafers",
            "product_name": "Sev Murmura Namkeen",
            "status": "COMPLIANT",
            "citation": "None",
            "details": "None (Fully compliant)",
            "mrp": "₹5.00",
            "net_qty": "26g",
            "usp": "₹0.19/g",
            "date": "06FEB26",
            "mfg": "Balaji Wafers Pvt. Ltd., Rajkot PIN 360021",
            "offset_hours": 138.0,
        },
        {
            "filename": "20_balaji_khatta_mitha_back_compliant.jpg",
            "brand": "Balaji Wafers",
            "product_name": "Khatta Mitha Mix",
            "status": "COMPLIANT",
            "citation": "None",
            "details": "None (Fully compliant)",
            "mrp": "₹10.00",
            "net_qty": "40g",
            "usp": "₹0.25/g",
            "date": "06FEB26",
            "mfg": "Balaji Wafers Pvt. Ltd., Rajkot PIN 360021",
            "offset_hours": 144.0,
        },
        {
            "filename": "30_royal_toast_elaichi_front_pdp.jpg",
            "brand": "Royal Bakery",
            "product_name": "Real Elaichi Toasted Bread",
            "status": "COMPLIANT",
            "citation": "None",
            "details": "None (Fully compliant)",
            "mrp": "₹30.00",
            "net_qty": "150g",
            "usp": "₹0.20/g",
            "date": "2026",
            "mfg": "Royal Bakeries Pvt. Ltd., Mumbai PIN 400050",
            "offset_hours": 148.0,
        },
        {
            "filename": "26_packaged_staple_missing_consumer_care.jpg",
            "brand": "Generic Brand",
            "product_name": "Packaged Food Grain",
            "status": "VIOLATION",
            "citation": "Rule 6(2)",
            "details": "Consumer Care contact details absent",
            "mrp": "₹60.00",
            "net_qty": "1kg",
            "usp": "₹0.06/g",
            "date": "2026",
            "mfg": "Regional Agro Packagers, Indore PIN 452001",
            "offset_hours": 152.0,
        },
        {
            "filename": "28_beverage_pouch_angled_review.jpg",
            "brand": "Beverage Brand",
            "product_name": "Fruit Drink Pouch",
            "status": "REVIEW",
            "citation": "Rule 8(1)",
            "details": "Geometry Review: Extreme camera perspective angle requires confirmation",
            "mrp": "₹20.00",
            "net_qty": "200ml",
            "usp": "₹0.10/ml",
            "date": "2026",
            "mfg": "Beverage Bottling Co., Nashik PIN 422001",
            "offset_hours": 156.0,
        },
        {
            "filename": "90_vim_dishwash_gel_pouch_front.jpg",
            "brand": "Vim",
            "product_name": "Lemon Dishwash Gel Pouch",
            "status": "COMPLIANT",
            "citation": "None",
            "details": "None (Fully compliant)",
            "mrp": "₹35.00",
            "net_qty": "250ml",
            "usp": "₹0.14/ml",
            "date": "08/2026",
            "mfg": "Hindustan Unilever Limited, Mumbai PIN 400099",
            "offset_hours": 160.0,
        },
        {
            "filename": "24_dark_fantasy_bourbon_mrp_compliant.jpg",
            "brand": "Sunfeast",
            "product_name": "Dark Fantasy Bourbon Cookies",
            "status": "COMPLIANT",
            "citation": "None",
            "details": "None (Fully compliant)",
            "mrp": "₹142.00",
            "net_qty": "450g",
            "usp": "₹0.32/g",
            "date": "04/08/26",
            "mfg": "ITC Limited, Kolkata PIN 700071",
            "offset_hours": 164.0,
        },
        {
            "filename": "03_balaji_mungdal_pdp_missing_netqty.jpg",
            "brand": "Balaji Wafers",
            "product_name": "Mung Dal Savouries",
            "status": "VIOLATION",
            "citation": "Rule 6(1)(c)",
            "details": "Net Quantity omitted on Principal Display Panel",
            "mrp": "₹5.00",
            "net_qty": None,
            "usp": "₹0.21/g",
            "date": "06FEB26",
            "mfg": "Balaji Wafers Pvt. Ltd., Rajkot PIN 360021",
            "offset_hours": 166.0,
        },
    ]

    # Delete existing test rows for officer 2 to ensure pristine display
    c.execute("DELETE FROM inspections WHERE officer_id = 2")
    print(f"Cleared previous test scans for officer_id = 2.")

    inserted = 0
    for p in products:
        insp_id = str(uuid.uuid4())
        created_dt = now - timedelta(hours=p["offset_hours"])
        created_str = created_dt.strftime("%Y-%m-%d %H:%M:%S")

        is_comp = p["status"] == "COMPLIANT"
        is_rev = p["status"] == "REVIEW"

        declarations = generate_declarations(p)
        comp_count = sum(1 for d in declarations if d["compliant"])
        non_comp_count = len(declarations) - comp_count

        if is_comp:
            summary = "✅ COMPLIANT: All statutory declarations on package panel comply with LMPC Rules 2011."
        elif is_rev:
            summary = f"⚠️ REVIEW REQUIRED: {p['details']} [{p['citation']}]."
        else:
            summary = f"⚠️ NON-COMPLIANT: {p['details']} [{p['citation']}]."

        raw_hash = hashlib.sha256(f"{p['filename']}_{insp_id}".encode()).hexdigest()

        c.execute("""
            INSERT INTO inspections (
                id, officer_id, image_filename, image_hash_sha256,
                overall_compliant, total_fields, compliant_fields, non_compliant_fields,
                summary, declarations_json, raw_ocr_json, dpi_used, created_at,
                calibration_method, reference_size_mm, pixels_per_mm, calibration_confidence,
                font_review_required, coverage_review_required, technical_verification_coverage
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            insp_id,
            2,  # officer_verma
            p["filename"],
            raw_hash,
            1 if is_comp else 0,
            len(declarations),
            comp_count,
            non_comp_count,
            summary,
            json.dumps(declarations),
            json.dumps([]),
            300,
            created_str,
            "aruco_40mm",
            40.0,
            11.81,
            0.96 if not is_rev else 0.52,
            1 if is_rev else 0,
            0,
            94.5 if is_comp else 76.0,
        ))
        inserted += 1

    conn.commit()
    conn.close()
    print(f"Successfully seeded {inserted} dataset products for Officer Rajesh Verma!")

if __name__ == "__main__":
    seed_database()
