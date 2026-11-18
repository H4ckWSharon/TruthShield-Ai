import os
from datetime import datetime, timezone
from typing import Dict, Any, List
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from app.core.config import settings

PLATFORM_POLICIES = {
    "youtube": {
        "name": "YouTube Community Guidelines",
        "sections": [
            "Harassment & Cyberbullying Policy (Clause 4.1)",
            "Impersonation Policy (Channel identity spoofing)",
            "Non-consensual sexual content / privacy violations",
            "Misinformation & synthetic media disclosure rules"
        ],
        "reporting_url": "https://www.youtube.com/reportabuse"
    },
    "instagram": {
        "name": "Instagram Community Standards & Meta Safety Center",
        "sections": [
            "Bullying & Harassment Guidelines (Section 3)",
            "Non-Consensual Sexual Imagery (NCII) Zero-Tolerance Protocol",
            "Inauthentic Behavior & Impersonation Policy",
            "Misinformation & Coercion Safeguards"
        ],
        "reporting_url": "https://help.instagram.com/192435014247952"
    },
    "facebook": {
        "name": "Facebook Community Standards",
        "sections": [
            "Privacy Violations and Image Rights (Section 12)",
            "Harassment and Extortion Standards",
            "Account Integrity and Authentic Identity",
            "Coordinated Inauthentic Behavior"
        ],
        "reporting_url": "https://www.facebook.com/help/1380418588640631"
    },
    "general_web": {
        "name": "Digital Millennium Copyright Act (DMCA) & Host Abuse Terms",
        "sections": [
            "Standard Notice & Takedown Procedure (17 U.S.C. 512)",
            "Hosting Provider Terms of Service Violation (Abuse)",
            "Right of Publicity and Unauthorized Likeness Usage"
        ],
        "reporting_url": "https://lookup.icann.org/"
    },
    "incident": {
        "name": "Enterprise Cybersecurity Incident & Digital Forensic Report",
        "sections": [
            "Forensic Evidence Preservation (ISO/IEC 27037)",
            "Brand Impersonation & Phishing Attack Vector",
            "Unauthorized Digital Asset Distribution",
            "Information Security Threat Assessment"
        ],
        "reporting_url": "https://www.alphardcrucis.com/security"
    }
}

def generate_pdf_report(
    case_data: Dict[str, Any],
    template_type: str = "incident",
    evidence_list: List[Dict[str, Any]] = None,
    analysis_list: List[Dict[str, Any]] = None,
    output_filename: str = None
) -> str:
    """
    Generate an authoritative, branded forensic PDF report for digital content protection.
    """
    evidence_list = evidence_list or []
    analysis_list = analysis_list or []
    
    if not output_filename:
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        case_id = case_data.get("case_number", "CASE").replace("-", "_")
        output_filename = f"TruthShield_Report_{case_id}_{timestamp_str}.pdf"

    output_path = settings.REPORTS_DIR / output_filename
    
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    
    # Custom Theme Styles
    navy_color = colors.HexColor("#0B132B")
    blue_color = colors.HexColor("#1C2541")
    cyan_color = colors.HexColor("#00B4D8")
    dark_gray = colors.HexColor("#333333")
    light_bg = colors.HexColor("#F4F6F9")
    critical_red = colors.HexColor("#D90429")

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=navy_color
    )
    
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        textColor=cyan_color,
        leading=14
    )

    meta_label_style = ParagraphStyle(
        "MetaLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=colors.HexColor("#4A5568")
    )
    
    body_style = ParagraphStyle(
        "ReportBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=dark_gray
    )

    section_heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=navy_color,
        spaceBefore=10,
        spaceAfter=4
    )

    story = []

    # Header / Branding Banner
    header_data = [
        [
            Paragraph("<b>TRUTHSHIELD AI</b> | Forensic Incident Report", title_style),
            Paragraph(f"<b>{settings.COMPANY_NAME}</b><br/>{settings.TAGLINE}", ParagraphStyle("Sub", fontName="Helvetica", fontSize=8, alignment=2, textColor=dark_gray))
        ]
    ]
    header_table = Table(header_data, colWidths=[360, 180])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(header_table)
    story.append(HRFlowable(width="100%", thickness=2, color=cyan_color, spaceBefore=6, spaceAfter=12))

    # Case Summary Meta Table
    case_num = case_data.get("case_number", "N/A")
    category = str(case_data.get("category", "General")).upper()
    status_str = str(case_data.get("status", "Detected")).replace("_", " ").upper()
    risk_level = str(case_data.get("risk_level", "Medium")).upper()
    report_date = datetime.now(timezone.utc).strftime("%B %d, %Y - %H:%M UTC")

    meta_rows = [
        [
            Paragraph("<b>Case Reference:</b>", meta_label_style), Paragraph(case_num, body_style),
            Paragraph("<b>Generated Date:</b>", meta_label_style), Paragraph(report_date, body_style)
        ],
        [
            Paragraph("<b>Incident Category:</b>", meta_label_style), Paragraph(category, body_style),
            Paragraph("<b>Platform Scope:</b>", meta_label_style), Paragraph(template_type.upper(), body_style)
        ],
        [
            Paragraph("<b>Current Status:</b>", meta_label_style), Paragraph(status_str, body_style),
            Paragraph("<b>Assessed Risk Level:</b>", meta_label_style),
            Paragraph(f"<font color='{critical_red if risk_level in ('HIGH', 'CRITICAL') else navy_color}'><b>{risk_level}</b></font>", body_style)
        ]
    ]
    meta_table = Table(meta_rows, colWidths=[120, 150, 120, 150])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), light_bg),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 10))

    # Case Description
    story.append(Paragraph("1. Incident Summary & Context", section_heading))
    desc_text = case_data.get("description") or "No additional description recorded by investigator."
    story.append(Paragraph(desc_text, body_style))
    story.append(Spacer(1, 8))

    # Submitted URLs
    urls = case_data.get("urls", [])
    if urls:
        story.append(Paragraph("2. Target URLs / Dissemination Endpoints", section_heading))
        url_data = [[Paragraph("<b>Target URL</b>", meta_label_style)]]
        for u in urls[:5]:
            url_data.append([Paragraph(f"<font color='#0066CC'><u>{u}</u></font>", body_style)])
        url_table = Table(url_data, colWidths=[540])
        url_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), light_bg),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(url_table)
        story.append(Spacer(1, 8))

    # Evidence & Cryptographic Verification
    story.append(Paragraph("3. Forensic Evidence & Cryptographic Integrity", section_heading))
    if evidence_list:
        ev_data = [[
            Paragraph("<b>Filename</b>", meta_label_style),
            Paragraph("<b>Type</b>", meta_label_style),
            Paragraph("<b>SHA-256 Digest</b>", meta_label_style)
        ]]
        for ev in evidence_list[:6]:
            ev_data.append([
                Paragraph(ev.get("original_filename", "N/A"), body_style),
                Paragraph(ev.get("evidence_type", "image"), body_style),
                Paragraph(f"<font size='7'>{ev.get('sha256_hash', 'N/A')}</font>", body_style)
            ])
        ev_table = Table(ev_data, colWidths=[160, 80, 300])
        ev_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), light_bg),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(ev_table)
    else:
        story.append(Paragraph("No direct media files attached to this case record.", body_style))
    story.append(Spacer(1, 8))

    # Relevant Platform Policy Citations
    policy_info = PLATFORM_POLICIES.get(template_type, PLATFORM_POLICIES["incident"])
    story.append(Paragraph(f"4. Platform Policy References ({policy_info['name']})", section_heading))
    policy_bullets = ""
    for sec in policy_info["sections"]:
        policy_bullets += f"• <b>{sec}</b><br/>"
    story.append(Paragraph(policy_bullets, body_style))
    story.append(Paragraph(f"Official Submission Channel: <font color='#0066CC'>{policy_info['reporting_url']}</font>", body_style))
    story.append(Spacer(1, 8))

    # Recommended Actions & Legal Safeguards
    story.append(Paragraph("5. Recommended Remediation & Legal Actions", section_heading))
    rec_text = (
        "1. Submit formal notice through the designated platform reporting channel citing specific policy sections listed above.<br/>"
        "2. Preserve the cryptographic SHA-256 evidence digests and this official report for potential legal escrow or law enforcement disclosure.<br/>"
        "3. Configure TruthShield Perceptual Fingerprint monitoring to intercept re-uploads across authorized archives."
    )
    story.append(Paragraph(rec_text, body_style))
    story.append(Spacer(1, 10))

    # Disclaimer / Footer
    disclaimer_text = (
        "<b>LEGAL & COMPLIANCE NOTICE:</b> This document is generated by TruthShield AI (Alphard Crucis Private Limited) "
        "as an evidence compilation report. AI confidence indicators and rule heuristic findings are investigative aids "
        "and do not constitute self-executing legal judgments or confirmation of third-party platform removal."
    )
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CBD5E1"), spaceBefore=6, spaceAfter=6))
    story.append(Paragraph(disclaimer_text, ParagraphStyle("Disc", fontName="Helvetica", fontSize=7, leading=9, textColor=colors.HexColor("#64748B"))))

    doc.build(story)
    return str(output_path)
