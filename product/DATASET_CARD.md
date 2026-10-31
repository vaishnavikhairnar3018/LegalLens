# LenseScan — Indian Packaged Commodities LMPC Benchmark Dataset

**Problem Statement:** Smart India Hackathon (SIH 26034)  
**Ministry:** Consumer Affairs, Food & Public Distribution  
**Statutory Benchmark:** Legal Metrology (Packaged Commodities) Rules, 2011 (LMPC Rules)  
**Dataset Version:** 2.0 (Complete 93-Image Audited Corpus)  
**Last Updated:** 2026-09-21 19:54 UTC

---

## 1. Dataset Overview

This dataset contains **93 genuine photographs** covering **21 distinct commercial FMCG product lines** across India:
- **Snacks & Namkeen:** Balaji Papdi Gathiya, Balaji Mung Dal, Balaji Sev Murmura, Balaji Khatta Mitha, Ram Bandhu Chakali Mix
- **Bakery & Rusks:** Royal Elaichi Toast, Haldiram Rusky Atta Toast, Bishnoi Foods Special Atta Toast
- **Biscuits & Confectionery:** Sunfeast Dark Fantasy Bourbon Cookies, Britannia NutriChoice Digestive, Vikas Sweet Candy
- **Instant Foods & Mixes:** Ching's Secret Manchow Soup, Samrat Swadomay Instant Khaman Dhokla
- **Packaged Staples & Dry Fruits:** Samrat MP Maida Flour, Packaged Food Grain, Amin Persian Wet Dates (Faaris International)
- **Condiments & Sauces:** Maggi Pichkoo Rich Tomato Ketchup, Suruchi Dark Soy Sauce
- **Personal Care & Insecticides:** Pond's Dreamflower Talc, Goodknight Flash Liquid Vaporiser
- **Household & Laundry Care:** Mysore Sandal Kleenol Cleaner, Surf Excel Stain Eraser Bar, Vim Lemon Dishwash Bar & Gel, Laundry Detergent Cap

Every image is cryptographically stamped with a **SHA-256 hash** upon capture, fulfilling the statutory chain-of-custody requirement for **Section 65B of the Indian Evidence Act**.

### Summary Statistics
| Metric | Count | Percentage |
| :--- | :---: | :---: |
| **Total Images** | **93** | 100.0% |
| **Fully Compliant Panels** | 76 | 81.7% |
| **Ground-Truth Statutory Violations** | 14 | 15.1% |
| **Geometry / Fallback Reviews** | 3 | 3.2% |

---

## 2. Statutory Violations & Edge Cases Covered

1. **Rule 6(1)(e) — Absence of Maximum Retail Price (MRP):**
   - Packaged goods missing conspicuous, tax-inclusive MRP declarations.
2. **Rule 6(1)(c) & Rule 12 — Omission of Net Quantity:**
   - Real industrial defect where net quantity numerical value/unit was blanked during batch laser/inkjet coding.
3. **Rule 7(2) — Minimum Font Size Non-Compliance:**
   - Mandatory declaration font heights rendered below statutory limits relative to Principal Display Panel area.
4. **Rule 6(1)(d) — Date of Manufacture / Packing / Expiry:**
   - Absence of manufacturing date or month/year stamp.
5. **Rule 6(2) — Consumer Grievance Coordinates:**
   - Omission of telephone, email, or postal grievance redressal addresses.
6. **Rule 8(1) — Crimp Seam / Placement Non-Compliance:**
   - Mandatory text stamped across heat seals, folds, or distorted along cylindrical canister radiuses.

---

## 3. Data Dictionary (`metadata.csv`)

| Column Name | Type | Description |
| :--- | :--- | :--- |
| `image_id` | String | Unique sample ID (`LMP_001` to `LMP_093`) |
| `filename` | String | Standardized self-describing filename |
| `brand` | String | Commercial brand (e.g., Balaji, Nestlé, Godrej, HUL, Britannia) |
| `product_name` | String | Specific product name & packaging variant |
| `category` | String | Industry commodity sector |
| `packaging_type` | String | Packaging form factor (Pillow Pouch, Spout Pouch, Box, Canister, Bottle) |
| `panel_type` | String | Specific packaging face photographed |
| `ground_truth_status` | Enum | `COMPLIANT`, `VIOLATION`, `REVIEW` |
| `statutory_citations` | String | Legal Metrology Rule citation (e.g., Rule 6(1)(e), Rule 7(2)) |
| `violation_details` | String | Description of statutory defect |
| `declared_mrp` | String | Extracted/labeled MRP value |
| `declared_net_qty` | String | Extracted/labeled Net Quantity |
| `declared_usp` | String | Unit Sale Price under Rule 6(11) |
| `declared_date` | String | Date of packing / manufacture / expiry |
| `manufacturer` | String | Declared manufacturing or marketing entity |
| `has_consumer_care` | Boolean | True if consumer care redressal details are present |
| `width_px` | Integer | Image width in pixels |
| `height_px` | Integer | Image height in pixels |
| `aspect_ratio` | Float | Width / Height aspect ratio |
| `size_kb` | Float | File size in Kilobytes |
| `sha256_hash` | String | 64-character SHA-256 evidence integrity hash |

---

## 4. Section 65B Evidence Integrity

All hashes in `metadata.csv` match the raw camera byte streams:
```python
import hashlib
digest = hashlib.sha256(open(filename, 'rb').read()).hexdigest()
```
This guarantees anti-tampering and statutory validity under **Section 65B of the Indian Evidence Act**.
