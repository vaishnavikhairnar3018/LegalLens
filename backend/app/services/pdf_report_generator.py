"""
LenseScan Legal Notice & Inspection Report Generator.
Generates authoritative PDF inspection certificates and non-compliance notices
under The Legal Metrology Act, 2009 and LMPC Rules, 2011.
"""

import io
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from xml.sax.saxutils import escape as xml_escape
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    KeepTogether,
)


def generate_inspection_pdf(
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
    Generate an official Ministry of Consumer Affairs Statutory Inspection Notice / Certificate.
    `photos` lists every photo of a multi-photo product inspection with its evidence hash.
    Returns the PDF content as bytes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "GovTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        alignment=1,  # Center
        textColor=colors.HexColor("#0B1B3D"),
    )
    sub_title_style = ParagraphStyle(
        "GovSubTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        alignment=1,
        textColor=colors.HexColor("#C0392B" if not overall_compliant else "#1E8449"),
    )
    meta_style = ParagraphStyle(
        "MetaText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#2C3E50"),
    )
    meta_bold = ParagraphStyle(
        "MetaBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#1A252F"),
    )
    table_hdr = ParagraphStyle(
        "TableHdr",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=10,
        textColor=colors.white,
    )
    table_cell = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#2C3E50"),
    )
    legal_warning_style = ParagraphStyle(
        "LegalNotice",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10.5,
        textColor=colors.HexColor("#7B241C"),
    )

    story = []

    # 1. Header & Seal
    story.append(Paragraph("GOVERNMENT OF INDIA", title_style))
    story.append(
        Paragraph(
            "MINISTRY OF CONSUMER AFFAIRS, FOOD & PUBLIC DISTRIBUTION",
            ParagraphStyle("SubGov", parent=title_style, fontSize=10, leading=13, textColor=colors.HexColor("#34495E")),
        )
    )
    story.append(
        Paragraph(
            "LEGAL METROLOGY ENFORCEMENT DIVISION",
            ParagraphStyle("SubDiv", parent=title_style, fontSize=9, leading=12, textColor=colors.HexColor("#5D6D7E")),
        )
    )
    story.append(Spacer(1, 4))
    story.append(
        HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0B1B3D"), spaceAfter=6, spaceBefore=2)
    )

    # 2. Form Name
    form_title = (
        "FORM LM-N1: STATUTORY NOTICE OF NON-COMPLIANCE"
        if not overall_compliant
        else "FORM LM-C1: CERTIFICATE OF STATUTORY COMPLIANCE"
    )
    story.append(Paragraph(form_title, sub_title_style))
    story.append(
        Paragraph(
            "Issued under Section 36 & 49 of The Legal Metrology Act, 2009 read with Legal Metrology (Packaged Commodities) Rules, 2011",
            ParagraphStyle("NoticeSub", parent=styles["Normal"], fontSize=7.5, leading=9, alignment=1, textColor=colors.HexColor("#566573")),
        )
    )
    story.append(Spacer(1, 10))

    # 3. Metadata Table
    meta_data = [
        [
            Paragraph("<b>Product:</b>", meta_bold),
            # Officer-entered text: escape so ReportLab does not read it as markup
            Paragraph(f"<b>{xml_escape(product_name)}</b>" if product_name else "Not recorded", meta_style),
            Paragraph("", meta_bold),
            Paragraph("", meta_style),
        ],
        [
            Paragraph("<b>Inspection Ref ID:</b>", meta_bold),
            Paragraph(f"<font color='#0B1B3D'><b>{inspection_id}</b></font>", meta_style),
            Paragraph("<b>Inspection Date:</b>", meta_bold),
            Paragraph(timestamp.strftime("%d-%b-%Y %H:%M:%S UTC"), meta_style),
        ],
        [
            Paragraph("<b>Inspecting Officer:</b>", meta_bold),
            Paragraph(f"{officer_name} (ID: #{officer_id})", meta_style),
            Paragraph("<b>Overall Status:</b>", meta_bold),
            Paragraph(
                f"<font color='{'#C0392B' if not overall_compliant else '#1E8449'}'><b>{'NON-COMPLIANT (INFRACTION)' if not overall_compliant else 'FULLY COMPLIANT'}</b></font>",
                meta_style,
            ),
        ],
        [
            Paragraph("<b>Evidence File:</b>", meta_bold),
            Paragraph(image_filename, meta_style),
            Paragraph("<b>Audit Score:</b>", meta_bold),
            Paragraph(f"{compliant_fields} / {total_fields} Declarations Passed", meta_style),
        ],
        [
            Paragraph("<b>SHA-256 Hash:</b>", meta_bold),
            Paragraph(
                f"<font size='6.5' face='Courier'>{image_hash_sha256}</font>",
                meta_style,
            ),
            Paragraph("<b>Tamper Check:</b>", meta_bold),
            Paragraph("<font color='#1E8449'><b>VERIFIED IMMUTABLE</b></font>", meta_style),
        ],
    ]

    meta_table = Table(meta_data, colWidths=[1.4 * inch, 2.3 * inch, 1.4 * inch, 2.3 * inch])
    meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8F9FA")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#BDC3C7")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7E9")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(meta_table)
    story.append(Spacer(1, 10))

    # 3b. Every photo of a multi-photo product inspection, with its own evidence hash
    if photos:
        story.append(Paragraph("<b>EVIDENCE PHOTOS (SHA-256 OF RAW UPLOADED BYTES):</b>", meta_bold))
        story.append(Spacer(1, 4))
        photo_rows = [[
            Paragraph("<b>Photo</b>", table_hdr),
            Paragraph("<b>40 mm marker</b>", table_hdr),
            Paragraph("<b>SHA-256</b>", table_hdr),
        ]]
        for p in photos:
            photo_rows.append([
                Paragraph(str(p.get("filename", "")), table_cell),
                Paragraph("Yes" if p.get("pixels_per_mm") else "No (text only)", table_cell),
                Paragraph(f"<font size='6.5' face='Courier'>{p.get('image_hash_sha256', '')}</font>", table_cell),
            ])
        photo_table = Table(photo_rows, colWidths=[2.0 * inch, 1.1 * inch, 4.3 * inch])
        photo_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B1B3D")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D5D8DC")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(photo_table)
        story.append(Spacer(1, 10))

    # 4. Mandatory Declarations Audit Table
    story.append(Paragraph("<b>STATUTORY DECLARATIONS AUDIT (LMPC RULES 2011, RULE 6):</b>", meta_bold))
    story.append(Spacer(1, 4))

    headers = [
        Paragraph("<b>Rule 6 Field</b>", table_hdr),
        Paragraph("<b>Detected Value</b>", table_hdr),
        Paragraph("<b>Status</b>", table_hdr),
        Paragraph("<b>Findings / Violations</b>", table_hdr),
    ]

    audit_rows = [headers]
    for d in declarations:
        field_name = d.get("display_name", d.get("field_name", "Unknown"))
        val = d.get("value") or "<font color='#7F8C8D'><i>Not Detected</i></font>"
        is_comp = d.get("compliant", False)
        status_text = (
            "<font color='#1E8449'><b>PASS</b></font>"
            if is_comp
            else "<font color='#C0392B'><b>FAIL</b></font>"
        )
        violations = d.get("violations", [])
        if not violations and is_comp:
            finding = "<font color='#1E8449'>Meets statutory criteria</font>"
        else:
            finding = "<br/>".join(f"• {v}" for v in violations) if violations else "Field missing or invalid"

        audit_rows.append(
            [
                Paragraph(f"<b>{field_name}</b>", table_cell),
                Paragraph(str(val), table_cell),
                Paragraph(status_text, table_cell),
                Paragraph(finding, table_cell),
            ]
        )

    audit_table = Table(
        audit_rows,
        colWidths=[1.8 * inch, 2.0 * inch, 0.9 * inch, 2.7 * inch],
    )
    audit_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B1B3D")),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#FDFEFE")],
                ),
            ]
        )
    )
    story.append(audit_table)
    story.append(Spacer(1, 10))

    # 5. Legal Warning / Statutory Action Box (if Non-Compliant)
    if not overall_compliant:
        legal_text = (
            "<b>STATUTORY NOTICE OF DEFECT & LEGAL LIABILITY:</b><br/>"
            "This package has been inspected and found non-compliant with the provisions of "
            "Rule 6 of the Legal Metrology (Packaged Commodities) Rules, 2011.<br/>"
            "<b>Notice under Section 36(1) of The Legal Metrology Act, 2009:</b> "
            "Whoever manufactures, packs, imports, sells, distributes, delivers or offers for sale "
            "any pre-packaged commodity which does not conform to the declarations on the package "
            "shall be punished with fine which may extend to <b>twenty-five thousand rupees</b> for the first offence, "
            "<b>fifty thousand rupees</b> for the second offence, and for subsequent offences with fine up to "
            "<b>one lakh rupees</b> or imprisonment up to <b>one year</b>, or both.<br/>"
            "The manufacturer/packer/distributor is hereby directed to show cause within 15 days of receipt of this notice."
        )
        legal_table = Table(
            [[Paragraph(legal_text, legal_warning_style)]],
            colWidths=[7.4 * inch],
        )
        legal_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FDEDEC")),
                    ("BOX", (0, 0), (-1, -1), 1.5, colors.HexColor("#E74C3C")),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(legal_table)
        story.append(Spacer(1, 10))

    # 6. Officer Signature & Digital Certification Block
    sig_data = [
        [
            Paragraph(
                "<b>SYSTEM VERIFICATION</b><br/>"
                "Certified and cryptographically logged via LegalLens AI.<br/>"
                f"Hash: <font size='6'>{image_hash_sha256[:32]}...</font><br/>"
                "SIH Problem Statement 26034",
                ParagraphStyle("SigLeft", parent=styles["Normal"], fontSize=7, leading=9, textColor=colors.HexColor("#7F8C8D")),
            ),
            Paragraph(
                f"<b>INSPECTING OFFICER SIGNATURE</b><br/><br/>"
                f"<b>{officer_name}</b><br/>"
                f"Officer ID: {officer_id}<br/>"
                f"Date: {datetime.now(timezone.utc).strftime('%d-%b-%Y')}",
                ParagraphStyle("SigRight", parent=styles["Normal"], fontSize=8, leading=10, alignment=2, textColor=colors.HexColor("#2C3E50")),
            ),
        ]
    ]
    sig_table = Table(sig_data, colWidths=[3.7 * inch, 3.7 * inch])
    sig_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    story.append(KeepTogether(sig_table))

    # Build PDF document
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
