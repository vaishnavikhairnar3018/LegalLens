"""
LenseScan DOCX Report Generator.
Generates editable Word documents (Form LM-N1 / Form LM-C1) mirroring
the statutory PDF content for editing by enforcement officials.
"""

import io
from datetime import datetime
from typing import Dict, Any, List, Optional

from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT


def generate_inspection_docx(
    inspection_id: str,
    officer_name: str,
    officer_id: int,
    image_filename: str,
    image_hash_sha256: str,
    timestamp: datetime,
    overall_compliant: bool,
    total_fields: int,
    compliant_fields: int,
    non_compliant_fields: int,
    summary: str,
    declarations: List[Dict[str, Any]],
    photos: Optional[List[Dict[str, Any]]] = None,
    product_name: Optional[str] = None,
) -> bytes:
    """
    Generate an editable Word document (DOCX) version of the
    Ministry of Consumer Affairs Statutory Inspection Notice / Certificate.
    `photos` lists every photo of a multi-photo product inspection with its evidence hash.
    Returns the DOCX content as bytes.
    """
    doc = Document()

    # Set default font
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Calibri'
    font.size = Pt(10)

    # Narrow margins
    for section in doc.sections:
        section.top_margin = Cm(1.5)
        section.bottom_margin = Cm(1.5)
        section.left_margin = Cm(2)
        section.right_margin = Cm(2)

    # ── Government Header ──
    header_para = doc.add_paragraph()
    header_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = header_para.add_run("GOVERNMENT OF INDIA")
    run.bold = True
    run.font.size = Pt(14)
    run.font.color.rgb = RGBColor(0x0A, 0x16, 0x28)

    ministry_para = doc.add_paragraph()
    ministry_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = ministry_para.add_run(
        "MINISTRY OF CONSUMER AFFAIRS, FOOD & PUBLIC DISTRIBUTION\n"
        "DEPARTMENT OF CONSUMER AFFAIRS\n"
        "LEGAL METROLOGY DIVISION"
    )
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor(0x1C, 0x35, 0x57)

    # ── Document Title ──
    doc.add_paragraph()  # spacer
    title_para = doc.add_paragraph()
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

    if overall_compliant:
        form_title = "FORM LM-C1: CERTIFICATE OF COMPLIANCE"
        form_subtitle = "Legal Metrology (Packaged Commodities) Rules, 2011"
    else:
        form_title = "FORM LM-N1: STATUTORY NON-COMPLIANCE NOTICE"
        form_subtitle = (
            "Under Section 36 of The Legal Metrology Act, 2009\n"
            "Legal Metrology (Packaged Commodities) Rules, 2011"
        )

    run = title_para.add_run(form_title)
    run.bold = True
    run.font.size = Pt(13)
    run.font.color.rgb = RGBColor(0xB9, 0x1C, 0x1C) if not overall_compliant else RGBColor(0x06, 0x6A, 0x50)

    sub_para = doc.add_paragraph()
    sub_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = sub_para.add_run(form_subtitle)
    run.italic = True
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor(0x64, 0x74, 0x8B)

    # ── Inspection Metadata ──
    doc.add_paragraph()
    meta_title = doc.add_paragraph()
    run = meta_title.add_run("INSPECTION DETAILS")
    run.bold = True
    run.font.size = Pt(11)

    # Metadata table
    meta_table = doc.add_table(rows=7, cols=2)
    meta_table.alignment = WD_TABLE_ALIGNMENT.LEFT
    meta_data = [
        ("Product:", product_name or "Not recorded"),
        ("Inspection ID:", inspection_id),
        ("Date & Time:", timestamp.strftime("%d %B %Y, %H:%M:%S IST") if timestamp else "—"),
        ("Inspecting Officer:", f"{officer_name} (ID: {officer_id})"),
        ("Image File:", image_filename),
        ("Evidence Hash (SHA-256):", image_hash_sha256),
        ("DPI Used:", "300"),
    ]
    for i, (label, value) in enumerate(meta_data):
        cell_label = meta_table.cell(i, 0)
        cell_label.text = label
        for paragraph in cell_label.paragraphs:
            for run in paragraph.runs:
                run.bold = True
                run.font.size = Pt(9)

        cell_value = meta_table.cell(i, 1)
        cell_value.text = value
        for paragraph in cell_value.paragraphs:
            for run in paragraph.runs:
                run.font.size = Pt(9)

    # ── Evidence photos (multi-photo product inspections) ──
    if photos:
        doc.add_paragraph()
        photos_title = doc.add_paragraph()
        run = photos_title.add_run("EVIDENCE PHOTOS (SHA-256 OF RAW UPLOADED BYTES)")
        run.bold = True
        run.font.size = Pt(11)
        photo_table = doc.add_table(rows=len(photos) + 1, cols=3)
        photo_table.style = 'Table Grid'
        for col, heading in enumerate(["Photo", "40 mm marker", "SHA-256"]):
            photo_table.cell(0, col).text = heading
        for row, p in enumerate(photos, start=1):
            photo_table.cell(row, 0).text = str(p.get("filename", ""))
            photo_table.cell(row, 1).text = "Yes" if p.get("pixels_per_mm") else "No (text only)"
            photo_table.cell(row, 2).text = str(p.get("image_hash_sha256", ""))
        for table_row in photo_table.rows:
            for cell in table_row.cells:
                for paragraph in cell.paragraphs:
                    for run in paragraph.runs:
                        run.font.size = Pt(8)

    # ── Compliance Summary ──
    doc.add_paragraph()
    summary_title = doc.add_paragraph()
    run = summary_title.add_run("COMPLIANCE SUMMARY")
    run.bold = True
    run.font.size = Pt(11)

    status_text = "COMPLIANT ✓" if overall_compliant else "NON-COMPLIANT ✗"
    status_para = doc.add_paragraph()
    run = status_para.add_run(f"Overall Status: {status_text}")
    run.bold = True
    run.font.size = Pt(12)
    run.font.color.rgb = RGBColor(0x06, 0x6A, 0x50) if overall_compliant else RGBColor(0xB9, 0x1C, 0x1C)

    score_para = doc.add_paragraph()
    score_para.add_run(
        f"Fields Checked: {total_fields}  |  "
        f"Compliant: {compliant_fields}  |  "
        f"Non-Compliant: {non_compliant_fields}"
    ).font.size = Pt(10)

    # ── Declarations Table ──
    doc.add_paragraph()
    decl_title = doc.add_paragraph()
    run = decl_title.add_run("DECLARATION AUDIT TABLE")
    run.bold = True
    run.font.size = Pt(11)

    # Table header
    decl_table = doc.add_table(rows=1, cols=5)
    decl_table.alignment = WD_TABLE_ALIGNMENT.LEFT
    headers = ["Declaration", "Status", "Detected Value", "Font (mm)", "Legal Rule"]
    header_cells = decl_table.rows[0].cells
    for i, h in enumerate(headers):
        header_cells[i].text = h
        for paragraph in header_cells[i].paragraphs:
            for run in paragraph.runs:
                run.bold = True
                run.font.size = Pt(8)

    # Table rows
    for decl in declarations:
        row = decl_table.add_row()
        field_name = decl.get("field_name", decl.get("display_name", "Unknown"))
        display_name = decl.get("display_name", field_name)
        detected = decl.get("detected", False)
        value = decl.get("value", "—") or "—"
        compliant = decl.get("compliant", True)
        font_mm = decl.get("font_height_mm")
        legal_rule = decl.get("legal_rule", decl.get("section_reference", "—"))
        violations = decl.get("violations", [])

        status_str = "✓ Compliant" if compliant else "✗ Violation"
        if not detected:
            status_str = "⊘ Missing"

        font_str = f"{font_mm:.1f}" if font_mm else "—"

        cells = row.cells
        cells[0].text = display_name
        cells[1].text = status_str
        cells[2].text = value[:60] if len(value) > 60 else value
        cells[3].text = font_str
        cells[4].text = str(legal_rule) if legal_rule else "—"

        for cell in cells:
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(8)

    # ── Violations Detail ──
    violation_decls = [d for d in declarations if d.get("violations")]
    if violation_decls:
        doc.add_paragraph()
        viol_title = doc.add_paragraph()
        run = viol_title.add_run("VIOLATIONS DETAIL")
        run.bold = True
        run.font.size = Pt(11)
        run.font.color.rgb = RGBColor(0xB9, 0x1C, 0x1C)

        for decl in violation_decls:
            display_name = decl.get("display_name", decl.get("field_name", "Unknown"))
            viol_para = doc.add_paragraph()
            run = viol_para.add_run(f"▸ {display_name}:")
            run.bold = True
            run.font.size = Pt(9)

            for v in decl.get("violations", []):
                bullet_para = doc.add_paragraph(style='List Bullet')
                run = bullet_para.add_run(v)
                run.font.size = Pt(9)

    # ── Legal Warning ──
    if not overall_compliant:
        doc.add_paragraph()
        warning_para = doc.add_paragraph()
        run = warning_para.add_run("⚠ STATUTORY WARNING")
        run.bold = True
        run.font.size = Pt(11)
        run.font.color.rgb = RGBColor(0xB9, 0x1C, 0x1C)

        legal_text = doc.add_paragraph()
        run = legal_text.add_run(
            "Under Section 36 of The Legal Metrology Act, 2009, any person who "
            "manufactures, packs, imports, sells, distributes or delivers any "
            "pre-packaged commodity which does not conform to the declarations "
            "required under the Act and Rules shall be punishable with fine which "
            "may extend to twenty-five thousand rupees for the first offence, and "
            "fifty thousand rupees for the second and subsequent offences. "
            "Continued contravention may result in imprisonment extending to one year."
        )
        run.font.size = Pt(9)
        run.italic = True

    # ── Summary Text ──
    doc.add_paragraph()
    summary_sec = doc.add_paragraph()
    run = summary_sec.add_run("INSPECTOR'S SUMMARY:")
    run.bold = True
    run.font.size = Pt(10)

    summary_text_para = doc.add_paragraph()
    run = summary_text_para.add_run(summary)
    run.font.size = Pt(9)

    # ── Signature Block ──
    doc.add_paragraph()
    doc.add_paragraph()
    sig_para = doc.add_paragraph()
    sig_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = sig_para.add_run(
        f"_________________________\n"
        f"{officer_name}\n"
        f"Legal Metrology Officer\n"
        f"Officer ID: {officer_id}"
    )
    run.font.size = Pt(9)

    # ── Footer ──
    doc.add_paragraph()
    footer_para = doc.add_paragraph()
    footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = footer_para.add_run(
        "This document was generated by LegalLens AI — Legal Metrology Compliance System\n"
        "Ministry of Consumer Affairs, Food & Public Distribution, Government of India\n"
        f"Evidence Hash: {image_hash_sha256}"
    )
    run.font.size = Pt(7)
    run.font.color.rgb = RGBColor(0x94, 0xA3, 0xB8)

    # Write to bytes
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.read()
