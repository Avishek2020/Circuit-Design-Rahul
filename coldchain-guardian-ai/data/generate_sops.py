"""
Generates 4 food-safety SOP PDFs into data/raw/sop_documents/.
Run: python data/generate_sops.py
"""

import os
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether,
)
from reportlab.platypus.flowables import HRFlowable
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw", "sop_documents")
os.makedirs(OUT_DIR, exist_ok=True)

# ── colour palette ────────────────────────────────────────────────────────────
BLUE_DARK  = colors.HexColor("#1a3a5c")
BLUE_MID   = colors.HexColor("#2e6da4")
BLUE_LIGHT = colors.HexColor("#ddeeff")
GREY_LIGHT = colors.HexColor("#f4f4f4")
GREY_MID   = colors.HexColor("#cccccc")
RED_ALERT  = colors.HexColor("#c0392b")
AMBER      = colors.HexColor("#e67e22")
GREEN_OK   = colors.HexColor("#27ae60")
WHITE      = colors.white
BLACK      = colors.black

# ── shared styles ─────────────────────────────────────────────────────────────
base = getSampleStyleSheet()

def make_styles():
    s = {}
    s["title"] = ParagraphStyle("sop_title",
        fontSize=20, fontName="Helvetica-Bold",
        textColor=WHITE, alignment=TA_CENTER,
        spaceAfter=4, leading=24)
    s["subtitle"] = ParagraphStyle("sop_subtitle",
        fontSize=11, fontName="Helvetica",
        textColor=WHITE, alignment=TA_CENTER, leading=14)
    s["meta"] = ParagraphStyle("sop_meta",
        fontSize=9, fontName="Helvetica",
        textColor=BLUE_MID, alignment=TA_CENTER, leading=12)
    s["h1"] = ParagraphStyle("sop_h1",
        fontSize=13, fontName="Helvetica-Bold",
        textColor=BLUE_DARK, spaceBefore=14, spaceAfter=4, leading=16,
        borderPad=4)
    s["h2"] = ParagraphStyle("sop_h2",
        fontSize=11, fontName="Helvetica-Bold",
        textColor=BLUE_MID, spaceBefore=10, spaceAfter=3, leading=14)
    s["body"] = ParagraphStyle("sop_body",
        fontSize=10, fontName="Helvetica",
        textColor=BLACK, spaceAfter=4, leading=14, alignment=TA_JUSTIFY)
    s["bullet"] = ParagraphStyle("sop_bullet",
        fontSize=10, fontName="Helvetica",
        textColor=BLACK, spaceAfter=3, leading=14,
        leftIndent=18, bulletIndent=6)
    s["note"] = ParagraphStyle("sop_note",
        fontSize=9, fontName="Helvetica-Oblique",
        textColor=colors.HexColor("#555555"), spaceAfter=4, leading=12,
        leftIndent=12)
    s["warn"] = ParagraphStyle("sop_warn",
        fontSize=10, fontName="Helvetica-Bold",
        textColor=RED_ALERT, spaceAfter=4, leading=14, leftIndent=12)
    s["cell_hdr"] = ParagraphStyle("cell_hdr",
        fontSize=9, fontName="Helvetica-Bold",
        textColor=WHITE, alignment=TA_CENTER, leading=12)
    s["cell"] = ParagraphStyle("cell",
        fontSize=9, fontName="Helvetica",
        textColor=BLACK, alignment=TA_LEFT, leading=12)
    s["cell_c"] = ParagraphStyle("cell_c",
        fontSize=9, fontName="Helvetica",
        textColor=BLACK, alignment=TA_CENTER, leading=12)
    s["footer"] = ParagraphStyle("footer",
        fontSize=8, fontName="Helvetica",
        textColor=colors.HexColor("#888888"), alignment=TA_CENTER)
    return s

ST = make_styles()

# ── page template with header/footer ─────────────────────────────────────────
class SopDoc(SimpleDocTemplate):
    def __init__(self, path, sop_number, title, revision, effective_date):
        super().__init__(
            path,
            pagesize=letter,
            topMargin=1.1 * inch,
            bottomMargin=0.85 * inch,
            leftMargin=0.85 * inch,
            rightMargin=0.85 * inch,
        )
        self.sop_number     = sop_number
        self.sop_title      = title
        self.sop_revision   = revision
        self.effective_date = effective_date

    def _header_footer(self, canvas, doc):
        canvas.saveState()
        w, h = letter
        # header bar
        canvas.setFillColor(BLUE_DARK)
        canvas.rect(0.85 * inch, h - 0.75 * inch,
                    w - 1.7 * inch, 0.4 * inch, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(0.95 * inch, h - 0.52 * inch,
                          f"ColdChain Guardian AI  |  {self.sop_number}: {self.sop_title}")
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(w - 0.95 * inch, h - 0.52 * inch,
                               f"Rev {self.sop_revision}  |  Effective: {self.effective_date}")
        # footer line + text
        canvas.setStrokeColor(GREY_MID)
        canvas.line(0.85 * inch, 0.65 * inch, w - 0.85 * inch, 0.65 * inch)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.setFont("Helvetica", 8)
        canvas.drawString(0.85 * inch, 0.45 * inch,
                          "CONFIDENTIAL – For Internal Use Only")
        canvas.drawCentredString(w / 2, 0.45 * inch,
                                 f"Page {doc.page}")
        canvas.drawRightString(w - 0.85 * inch, 0.45 * inch,
                               "© FrostGuard Logistics, Inc.")
        canvas.restoreState()

    def build(self, flowables, **kw):
        super().build(flowables,
                      onFirstPage=self._header_footer,
                      onLaterPages=self._header_footer,
                      **kw)

# ── reusable builders ─────────────────────────────────────────────────────────

def cover_block(sop_num, title, subtitle, revision, eff, review, owner, approver):
    """Blue banner cover block."""
    banner_data = [[
        Paragraph(sop_num, ST["subtitle"]),
        Paragraph(title,    ST["title"]),
        Paragraph(subtitle, ST["subtitle"]),
    ]]
    banner = Table(banner_data, colWidths=[6.8 * inch])
    banner.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, -1), BLUE_DARK),
        ("TOPPADDING",  (0, 0), (-1, -1), 18),
        ("BOTTOMPADDING",(0,0), (-1, -1), 18),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING",(0, 0), (-1, -1), 12),
        ("ALIGN",       (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [BLUE_DARK]),
    ]))

    meta_rows = [
        [Paragraph("Document Number", ST["cell_hdr"]),
         Paragraph("Revision", ST["cell_hdr"]),
         Paragraph("Effective Date", ST["cell_hdr"]),
         Paragraph("Review Date", ST["cell_hdr"])],
        [Paragraph(sop_num, ST["cell_c"]),
         Paragraph(revision, ST["cell_c"]),
         Paragraph(eff, ST["cell_c"]),
         Paragraph(review, ST["cell_c"])],
        [Paragraph("Document Owner", ST["cell_hdr"]),
         Paragraph("Approver", ST["cell_hdr"]),
         Paragraph("Department", ST["cell_hdr"]),
         Paragraph("Classification", ST["cell_hdr"])],
        [Paragraph(owner, ST["cell_c"]),
         Paragraph(approver, ST["cell_c"]),
         Paragraph("Food Safety & Quality", ST["cell_c"]),
         Paragraph("Controlled", ST["cell_c"])],
    ]
    col_w = [1.7 * inch] * 4
    meta_tbl = Table(meta_rows, colWidths=col_w)
    meta_tbl.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, -1), GREY_LIGHT),
        ("BACKGROUND",  (0, 0), (-1, 0),  BLUE_MID),
        ("BACKGROUND",  (0, 2), (-1, 2),  BLUE_MID),
        ("GRID",        (0, 0), (-1, -1), 0.5, GREY_MID),
        ("TOPPADDING",  (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0,0), (-1, -1), 5),
        ("ALIGN",       (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return [banner, Spacer(1, 0.18 * inch), meta_tbl, Spacer(1, 0.14 * inch)]

def section(title):
    return [
        HRFlowable(width="100%", thickness=1.5, color=BLUE_MID, spaceAfter=4),
        Paragraph(title, ST["h1"]),
    ]

def subsection(title):
    return [Paragraph(title, ST["h2"])]

def body(text):
    return Paragraph(text, ST["body"])

def bullet(text):
    return Paragraph(f"• {text}", ST["bullet"])

def note(text):
    return Paragraph(f"<i>Note: {text}</i>", ST["note"])

def warn(text):
    return Paragraph(f"⚠  {text}", ST["warn"])

def numbered(n, text):
    return Paragraph(f"<b>{n}.</b>  {text}", ST["bullet"])

def std_table(headers, rows, col_widths=None, stripe=True):
    hrow = [Paragraph(h, ST["cell_hdr"]) for h in headers]
    data = [hrow]
    for r in rows:
        data.append([Paragraph(str(c), ST["cell"]) for c in r])
    if col_widths is None:
        col_widths = [6.8 * inch / len(headers)] * len(headers)
    t = Table(data, colWidths=col_widths)
    style_cmds = [
        ("BACKGROUND",   (0, 0), (-1, 0),  BLUE_DARK),
        ("GRID",         (0, 0), (-1, -1), 0.4, GREY_MID),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
    ]
    if stripe:
        for i in range(1, len(data)):
            bg = GREY_LIGHT if i % 2 == 0 else WHITE
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), bg))
    t.setStyle(TableStyle(style_cmds))
    return t

def revision_table(entries):
    headers = ["Rev", "Date", "Description of Change", "Author", "Approved By"]
    col_w   = [0.45*inch, 0.85*inch, 2.95*inch, 1.2*inch, 1.3*inch]
    return std_table(headers, entries, col_widths=col_w)

# ═════════════════════════════════════════════════════════════════════════════
# SOP-001  Temperature Monitoring and Control
# ═════════════════════════════════════════════════════════════════════════════

def build_sop_001():
    path = os.path.join(OUT_DIR, "SOP-001_Temperature_Monitoring_Control.pdf")
    doc  = SopDoc(path, "SOP-001",
                  "Temperature Monitoring and Control Procedures",
                  "3.1", "2024-09-01")
    story = []

    story += cover_block(
        "SOP-001",
        "Temperature Monitoring and Control Procedures",
        "Cold Chain Integrity | Refrigerated Transport & Storage",
        "3.1", "2024-09-01", "2025-09-01",
        "Dr. Patricia Wells, VP Food Safety",
        "Robert Huang, Chief Quality Officer",
    )

    # 1. Purpose
    story += section("1.  Purpose")
    story.append(body(
        "This Standard Operating Procedure defines the requirements for continuous temperature "
        "monitoring and control throughout all cold-chain operations at FrostGuard Logistics, Inc. "
        "It ensures that temperature-sensitive products — including fresh meat, dairy, produce, "
        "pharmaceuticals, and frozen goods — are maintained within specified ranges from point of "
        "origin to point of delivery, in full compliance with FDA 21 CFR Part 110, FSMA Preventive "
        "Controls Rule, and applicable HACCP Critical Control Point (CCP) requirements."
    ))

    # 2. Scope
    story += section("2.  Scope")
    story.append(body(
        "This SOP applies to all FrostGuard employees, contractors, and third-party carriers who "
        "handle temperature-controlled products. It covers refrigerated trailers, controlled-atmosphere "
        "containers, cold-storage warehouse zones, and all in-transit monitoring systems."
    ))

    # 3. Definitions
    story += section("3.  Definitions")
    defs = [
        ["Term", "Definition"],
        ["Critical Control Point (CCP)",
         "A step at which a control measure can be applied to prevent, eliminate, or reduce a food-safety hazard to an acceptable level."],
        ["Temperature Excursion",
         "Any deviation of product temperature outside the validated acceptable range lasting more than 15 consecutive minutes."],
        ["Critical Limit",
         "The maximum and/or minimum value to which a CCP must be controlled to prevent, eliminate, or reduce a food-safety hazard."],
        ["Corrective Temperature Range",
         "An intermediate range outside the optimal range but within which product quality may be preserved pending investigation."],
        ["HACCP",
         "Hazard Analysis and Critical Control Points – a systematic preventive approach to food safety."],
        ["Data Logger",
         "An electronic device that records temperature (and optionally humidity) at pre-set intervals throughout a shipment."],
        ["Mean Kinetic Temperature (MKT)",
         "A single calculated temperature that expresses the cumulative thermal stress experienced by a product over time."],
    ]
    tbl_data = [[Paragraph(r[0], ST["cell_hdr"] if i == 0 else ST["cell"]),
                 Paragraph(r[1], ST["cell_hdr"] if i == 0 else ST["cell"])]
                for i, r in enumerate(defs)]
    t = Table(tbl_data, colWidths=[1.8*inch, 5.0*inch])
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0),  BLUE_DARK),
        ("BACKGROUND",   (0, 1), (0, -1),  BLUE_LIGHT),
        ("GRID",         (0, 0), (-1, -1), 0.4, GREY_MID),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
        ("LEFTPADDING",  (0, 0), (-1, -1), 6),
        ("VALIGN",       (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.1*inch))

    # 4. Required temperature ranges
    story += section("4.  Required Temperature Ranges by Product Category")
    story.append(body(
        "The following table defines the critical limits established under HACCP Plan FG-HACCP-002. "
        "These limits supersede any carrier or shipper defaults."
    ))
    temp_rows = [
        ["Meat (fresh/chilled)",      "0°C to 4°C",    "-2°C to 7°C",   "Dispose if > 10°C for > 2 h",   "FDA 21 CFR 110"],
        ["Dairy (butter/cream/cheese)","1°C to 4°C",   "0°C to 6°C",    "Quarantine; lab test required",  "PMO Grade A"],
        ["Fresh Produce",             "2°C to 8°C",    "0°C to 12°C",   "Inspect; supplier approval req.", "USDA AMS"],
        ["Pharmaceutical / Biologics","2°C to 8°C",    "0°C to 10°C",   "Dispose; FDA notification req.", "USP <1079>"],
        ["Seafood (fresh/chilled)",   "-2°C to 2°C",   "-4°C to 4°C",   "Dispose if > 7°C for > 1 h",    "FDA SSOP"],
        ["Frozen goods",              "-25°C to -15°C","-27°C to -12°C","Dispose; CAPA required",          "FDA FSMA"],
    ]
    story.append(std_table(
        ["Product Category", "Critical Limit (CCP)", "Corrective Range", "Action if Exceeded", "Regulatory Ref."],
        temp_rows,
        col_widths=[1.25*inch, 1.2*inch, 1.2*inch, 1.75*inch, 1.4*inch],
    ))
    story.append(Spacer(1, 0.08*inch))
    story.append(warn(
        "Any product exceeding the Critical Limit for more than 30 minutes must be quarantined "
        "immediately. The Food Safety Manager must be notified within 1 hour."
    ))

    # 5. Equipment
    story += section("5.  Monitoring Equipment and Calibration")
    story += subsection("5.1  Approved Sensor Systems")
    story.append(body(
        "All refrigerated vehicles must be equipped with a minimum of two (2) continuous-recording "
        "electronic temperature sensors: one positioned at the front (near refrigeration unit) and "
        "one at the rear of the cargo space. Sensors must meet the following specifications:"
    ))
    for b in [
        "Accuracy: ±0.5°C across the full operating range",
        "Resolution: 0.1°C minimum",
        "Recording interval: ≤ 15 minutes during transit; ≤ 30 minutes during stationary storage",
        "Battery life: ≥ 72 hours continuous operation",
        "Alarm threshold: configurable; must be set to trigger at ±1°C of the Critical Limit",
        "Data retrieval: Bluetooth or USB; NIST-traceable calibration certificate required",
    ]:
        story.append(bullet(b))

    story += subsection("5.2  Calibration Schedule")
    cal_rows = [
        ["In-vehicle temperature sensors",   "Every 6 months",   "Certified calibration laboratory",    "FG-CAL-001"],
        ["Warehouse zone thermometers",       "Every 3 months",   "In-house; NIST thermometer reference","FG-CAL-002"],
        ["Handheld probe thermometers",       "Before each use",  "Ice-water reference (0°C ±0.5°C)",   "FG-CAL-003"],
        ["Data loggers (portable)",           "Annually",         "Certified calibration laboratory",    "FG-CAL-004"],
    ]
    story.append(std_table(
        ["Equipment", "Frequency", "Method", "Record Form"],
        cal_rows,
        col_widths=[1.8*inch, 1.3*inch, 2.4*inch, 1.3*inch],
    ))

    # 6. Monitoring procedure
    story += section("6.  Temperature Monitoring Procedure")
    story += subsection("6.1  Pre-Departure Checks")
    for i, s in enumerate([
        "Verify refrigeration unit has pre-cooled to within critical range (minimum 2 hours prior to loading).",
        "Record pre-load temperature on Form FG-TMP-001 (Pre-Departure Temperature Log).",
        "Confirm data loggers are active and recording; note start time and sensor ID.",
        "Inspect door seals for cracks, compression failure, or debris. Replace if damaged.",
        "Complete checklist FG-VEH-002 (Vehicle Pre-Trip Inspection) and obtain driver signature.",
        "If pre-load temperature is outside range, do NOT load product. Notify Dispatch and Food Safety.",
    ], 1):
        story.append(numbered(i, s))

    story += subsection("6.2  During Transit")
    for i, s in enumerate([
        "Drivers must check the cab-mounted temperature display every 2 hours and log readings.",
        "If an alarm activates, the driver must stop at the nearest safe location, record the temperature, "
        "and call the 24/7 Incident Hotline (+1-800-555-0199) immediately.",
        "Door openings must be minimised. Each opening must be logged with time, location, and reason.",
        "Re-entry into temperature range must be confirmed before resuming transport.",
        "GPS and temperature data are transmitted in real-time to the Fleet Management System (FMS).",
    ], 1):
        story.append(numbered(i, s))

    story += subsection("6.3  Receiving and Unloading")
    for i, s in enumerate([
        "Receiving personnel must record trailer/container temperature before opening doors (Form FG-TMP-002).",
        "Product internal temperature must be verified using a calibrated probe thermometer on ≥ 10% of units.",
        "If product temperature exceeds the corrective range, quarantine all product and initiate Form FG-INC-001.",
        "Data logger must be retrieved and uploaded to the ColdChain Guardian AI platform within 4 hours.",
        "Signed Chain of Custody (Form FG-COC-001) must accompany all deliveries.",
    ], 1):
        story.append(numbered(i, s))

    # 7. Excursion response
    story += section("7.  Temperature Excursion Response Decision Tree")
    story.append(body(
        "When an excursion is detected, the following decision matrix determines required action. "
        "All decisions must be documented on Form FG-INC-001."
    ))
    exc_rows = [
        ["Minor (≤ 2°C above limit, < 15 min)",       "Amber", "Log and monitor; no product action required unless recurrence"],
        ["Moderate (2–5°C above limit, 15–60 min)",    "Orange","Quarantine product; notify Food Safety Manager; conduct CAPA"],
        ["Major (> 5°C above limit, OR > 60 min)",     "Red",   "Quarantine and segregate product; mandatory Food Safety review; "
                                                                 "potential disposal; regulatory notification assessment"],
        ["Critical (> 10°C above limit for frozen, "
         "OR > 15°C for chilled)",                     "Critical","Immediate disposal; FDA/USDA notification within 24 h; "
                                                                   "full root-cause investigation; CAPA mandatory"],
    ]
    story.append(std_table(
        ["Excursion Level", "Alert Colour", "Required Action"],
        exc_rows,
        col_widths=[2.1*inch, 0.9*inch, 3.8*inch],
    ))

    # 8. Records
    story += section("8.  Records and Retention")
    story.append(body(
        "All temperature records must be retained for a minimum of 3 years or as required by applicable "
        "regulations, whichever is longer. Electronic records stored in the ColdChain Guardian AI platform "
        "are automatically archived. Paper records must be scanned within 24 hours of completion."
    ))
    rec_rows = [
        ["FG-TMP-001", "Pre-Departure Temperature Log",        "Driver",               "3 years"],
        ["FG-TMP-002", "Receiving Temperature Record",         "Receiving Supervisor", "3 years"],
        ["FG-INC-001", "Temperature Excursion Incident Report","Food Safety Manager",  "5 years"],
        ["FG-CAL-001–004", "Calibration Certificates",        "Quality Dept.",        "Device life + 2 years"],
        ["FG-COC-001", "Chain of Custody Record",              "Driver / Receiver",    "3 years"],
    ]
    story.append(std_table(
        ["Form #", "Description", "Responsible Party", "Retention Period"],
        rec_rows,
        col_widths=[1.1*inch, 2.5*inch, 1.6*inch, 1.6*inch],
    ))

    # 9. Revision history
    story += section("9.  Revision History")
    story.append(revision_table([
        ["1.0", "2021-03-01", "Initial release",                               "P. Wells",   "R. Huang"],
        ["2.0", "2022-11-15", "Added pharmaceutical category; updated MKT guidance",
         "P. Wells",   "R. Huang"],
        ["3.0", "2023-08-20", "Integrated ColdChain Guardian AI platform requirements",
         "A. Khalil",  "R. Huang"],
        ["3.1", "2024-09-01", "Updated excursion decision matrix; added Section 7 alert colours",
         "P. Wells",   "R. Huang"],
    ]))

    doc.build(story)
    return path

# ═════════════════════════════════════════════════════════════════════════════
# SOP-002  Cold Chain Breach Response Protocol
# ═════════════════════════════════════════════════════════════════════════════

def build_sop_002():
    path = os.path.join(OUT_DIR, "SOP-002_Cold_Chain_Breach_Response.pdf")
    doc  = SopDoc(path, "SOP-002",
                  "Cold Chain Breach Response Protocol",
                  "2.4", "2024-07-15")
    story = []

    story += cover_block(
        "SOP-002",
        "Cold Chain Breach Response Protocol",
        "Emergency Response | Product Disposition | Regulatory Notification",
        "2.4", "2024-07-15", "2025-07-15",
        "Jennifer Park, Food Safety Manager",
        "Dr. Patricia Wells, VP Food Safety",
    )

    story += section("1.  Purpose")
    story.append(body(
        "This SOP establishes the structured response framework that must be activated whenever a "
        "confirmed or suspected cold-chain breach occurs. The goal is to protect public health, "
        "preserve evidence for investigation, comply with regulatory notification requirements, and "
        "minimise financial loss through timely, documented decision-making."
    ))

    story += section("2.  Scope and Trigger Conditions")
    story.append(body("This protocol is triggered by any of the following conditions:"))
    for b in [
        "A confirmed temperature excursion classified as Major or Critical (see SOP-001 §7)",
        "An automated alarm from the ColdChain Guardian AI platform indicating a breach lasting > 30 minutes",
        "A driver or warehouse employee reporting visible product deterioration or unexpected odour",
        "A receiving customer reporting a temperature anomaly on delivery",
        "Loss of real-time telemetry signal for more than 45 minutes during active transport",
        "A refrigeration unit failure alarm, with or without confirmed temperature deviation",
    ]:
        story.append(bullet(b))

    story += section("3.  Immediate Response (0–1 Hour)")
    story += subsection("3.1  Notification Chain")
    story.append(body(
        "Upon detection of a breach trigger, the following notification sequence must be completed "
        "within 60 minutes. Each recipient must acknowledge receipt."
    ))
    notif_rows = [
        ["0–5 min",   "Driver / Warehouse Staff",   "Activate alarm; secure product; call Incident Hotline 800-555-0199"],
        ["0–15 min",  "Dispatch Control",            "Log incident in FMS; deploy nearest inspection team if in transit"],
        ["5–20 min",  "Food Safety Manager (on-call)","Assess severity; authorise quarantine; initiate Form FG-INC-001"],
        ["15–30 min", "VP Food Safety",              "Assess regulatory reportability; contact Legal if Critical severity"],
        ["30–60 min", "Customer / Consignee",        "Notify of potential delay or product hold pending investigation"],
        ["< 24 h",    "Regulatory Authority",        "FDA/USDA notification if Critical severity (see §6)"],
    ]
    story.append(std_table(
        ["Timeframe", "Recipient", "Required Action"],
        notif_rows,
        col_widths=[0.85*inch, 1.85*inch, 4.1*inch],
    ))
    story.append(Spacer(1, 0.08*inch))
    story.append(warn(
        "No product involved in a Major or Critical breach may be released for sale or consumption "
        "without written authorisation from the Food Safety Manager AND the VP Food Safety."
    ))

    story += subsection("3.2  Product Quarantine Steps")
    for i, s in enumerate([
        "Physically separate suspect product from compliant product using red quarantine tape and signage.",
        "Apply a red 'HOLD' label (Form FG-HLD-001) to every pallet or case — include date, time, lot number.",
        "Do NOT dispose of product until a disposition decision is made (see §4).",
        "Preserve all data-logger records, sensor downloads, and vehicle GPS logs as evidence.",
        "Photograph all labels, temperature displays, and product condition before moving anything.",
        "Restrict access to quarantine area to Food Safety personnel only.",
    ], 1):
        story.append(numbered(i, s))

    story += section("4.  Product Disposition Decision Framework")
    story.append(body(
        "Product disposition must be decided by the Food Safety Manager in consultation with the VP "
        "Food Safety. The ColdChain Guardian AI incident analysis tool may be used to calculate Mean "
        "Kinetic Temperature (MKT) and provide an evidence-based recommendation."
    ))
    disp_rows = [
        ["All readings within corrective range; duration < 2 h",
         "Release with documentation",
         "No customer notification required; file FG-TMP-002"],
        ["Corrective range exceeded; duration 2–8 h; no organoleptic change",
         "Conditional release OR reprocess",
         "Lab testing required; customer notification at Food Safety Manager discretion"],
        ["Critical limit exceeded > 8 h; OR any duration for pharma products",
         "Quarantine pending lab results",
         "Mandatory lab testing; customer notification required"],
        ["Critical excursion with organoleptic signs of spoilage, OR pharma > any excursion",
         "Mandatory disposal",
         "FDA/USDA notification; CAPA; destruction witnessed and documented"],
    ]
    story.append(std_table(
        ["Condition", "Disposition", "Additional Requirements"],
        disp_rows,
        col_widths=[2.2*inch, 1.8*inch, 2.8*inch],
    ))

    story += section("5.  Root Cause Investigation")
    story.append(body(
        "All Major and Critical breaches require a formal Root Cause Analysis (RCA) completed within "
        "5 business days. The RCA must use the 5-Why methodology and produce a written CAPA report "
        "(Form FG-CAPA-001)."
    ))
    story += subsection("5.1  Common Root Causes and Preventive Actions")
    rca_rows = [
        ["Refrigeration unit mechanical failure",
         "Preventive maintenance schedule adherence; real-time compressor monitoring"],
        ["Door seal failure / improper closure",
         "Pre-trip seal inspection; driver training; automated door-status alerts"],
        ["Extended idling / power-off during stops",
         "Auxiliary power unit (APU) requirement for stops > 30 min; driver training"],
        ["Route deviation causing extended transit time",
         "Real-time GPS monitoring; dispatcher authority to reroute; buffer time in scheduling"],
        ["Pre-cooling non-compliance",
         "Automated gate-lock: trailer cannot depart until pre-cool confirmed by FMS"],
        ["Sensor failure / data loss",
         "Dual-redundant sensors; cellular backup; 15-min no-data alert in FMS"],
    ]
    story.append(std_table(
        ["Root Cause Category", "Preventive Control Measure"],
        rca_rows,
        col_widths=[2.4*inch, 4.4*inch],
    ))

    story += section("6.  Regulatory Notification Requirements")
    story.append(body(
        "Regulatory notification obligations depend on product type, severity, and whether the product "
        "has entered commerce. Legal counsel must be consulted before any external notification."
    ))
    reg_rows = [
        ["FDA (Human Food)",       "Critical breach, pharma, or biologics",
         "Within 24 hours of confirmed breach",    "MedWatch / FDA Reportable Food Registry"],
        ["USDA FSIS",              "Meat, poultry, egg products",
         "Immediately upon discovery of adulteration",
         "USDA FSIS District Office"],
        ["State Health Dept.",     "Any product already distributed to consumers",
         "Within 24 hours",        "State-specific portal; Legal to advise"],
        ["Customer / Consignee",   "All Major / Critical breaches",
         "Within 4 hours of classification",
         "Written notification via email + phone call"],
    ]
    story.append(std_table(
        ["Authority", "Trigger", "Timeframe", "Method"],
        reg_rows,
        col_widths=[1.3*inch, 2.0*inch, 1.7*inch, 1.8*inch],
    ))

    story += section("7.  Revision History")
    story.append(revision_table([
        ["1.0", "2020-05-01", "Initial release",                                      "J. Park",  "P. Wells"],
        ["2.0", "2022-01-10", "Added pharma-specific disposition rules",              "P. Wells", "P. Wells"],
        ["2.3", "2023-10-05", "Integrated AI platform triggers; updated notification chain",
         "J. Park",  "P. Wells"],
        ["2.4", "2024-07-15", "Revised regulatory notification timeframes post-FSMA update",
         "A. Khalil","P. Wells"],
    ]))

    doc.build(story)
    return path

# ═════════════════════════════════════════════════════════════════════════════
# SOP-003  Vehicle Sanitation and Inspection Standards
# ═════════════════════════════════════════════════════════════════════════════

def build_sop_003():
    path = os.path.join(OUT_DIR, "SOP-003_Vehicle_Sanitation_Inspection.pdf")
    doc  = SopDoc(path, "SOP-003",
                  "Refrigerated Vehicle Sanitation and Inspection Standards",
                  "1.8", "2024-04-01")
    story = []

    story += cover_block(
        "SOP-003",
        "Refrigerated Vehicle Sanitation and Inspection Standards",
        "Fleet Hygiene | FSMA Sanitary Transportation Rule Compliance",
        "1.8", "2024-04-01", "2025-04-01",
        "Ahmed Khalil, Fleet Quality Manager",
        "Dr. Patricia Wells, VP Food Safety",
    )

    story += section("1.  Purpose")
    story.append(body(
        "This SOP defines sanitation and inspection requirements for all FrostGuard refrigerated "
        "trailers and containers in accordance with the FDA FSMA Sanitary Transportation of Human "
        "and Animal Food Rule (21 CFR Part 1, Subpart O). It ensures vehicles do not become a "
        "source of contamination and are fit for purpose before each load."
    ))

    story += section("2.  Sanitation Schedule")
    story += subsection("2.1  Routine Cleaning (Between Each Load)")
    story.append(body(
        "All trailers must be cleaned and inspected between each load of food products. The following "
        "steps must be performed by a certified sanitation technician or trained driver and recorded "
        "on Form FG-SAN-001 (Trailer Sanitation Log)."
    ))
    for i, s in enumerate([
        "Remove all previous load residue, packaging material, and debris.",
        "Pre-rinse interior surfaces with potable water at ≥ 50°C.",
        "Apply approved food-contact sanitiser (see Appendix A for approved chemicals and dilution rates).",
        "Scrub walls, floors, bulkheads, door gaskets, and refrigeration coil guards.",
        "Allow sanitiser contact time per manufacturer specification (minimum 2 minutes).",
        "Rinse thoroughly; no sanitiser residue acceptable on food-contact surfaces.",
        "Inspect and dry interior; leave doors open for minimum 15 minutes before reloading.",
        "Complete and sign Form FG-SAN-001; file with Dispatch.",
    ], 1):
        story.append(numbered(i, s))

    story += subsection("2.2  Deep Sanitation (Monthly and After Non-Food Loads)")
    story.append(body(
        "Deep sanitation must be performed monthly and immediately after any non-food cargo, "
        "confirmed pest activity, spillage of allergen-containing products, or following a "
        "Critical breach incident. Deep sanitation requires a licensed third-party sanitation vendor."
    ))
    deep_rows = [
        ["Monthly scheduled",                 "Every 30 days",    "Third-party vendor",   "FG-SAN-002"],
        ["Post non-food load",                "After each occurrence","Third-party vendor","FG-SAN-002"],
        ["Post allergen spill",               "Immediately",      "Third-party vendor",   "FG-SAN-003"],
        ["Post Critical temperature breach",  "Before return to service","Third-party vendor","FG-SAN-004"],
        ["Pest activity confirmed",           "Immediately; vehicle OOS","Third-party vendor + PCO","FG-SAN-005"],
    ]
    story.append(std_table(
        ["Trigger", "Timing", "Responsible Party", "Form #"],
        deep_rows,
        col_widths=[2.2*inch, 1.5*inch, 1.6*inch, 1.5*inch],
    ))

    story += section("3.  Pre-Trip Inspection Checklist")
    story.append(body(
        "Drivers must complete the following physical inspection before accepting a load. Any item "
        "marked FAIL must be reported to Fleet Maintenance before departure. Vehicles must not be "
        "loaded until all FAIL items are resolved and re-inspected."
    ))
    chk_rows = [
        ["Refrigeration unit – operation status",        "Start unit; verify reaches set-point in ≤ 45 min"],
        ["Refrigeration unit – unusual noises/vibration","Listen during operation; note any abnormality"],
        ["Door seals – condition and compression",       "Visual + physical press test; no gaps, cracks, or hardening"],
        ["Door hinges and latches",                      "Operate doors fully; confirm latches engage securely"],
        ["Interior walls and floor – cleanliness",       "No debris, moisture, odour, or residue from prior load"],
        ["Interior walls – structural integrity",        "No holes, exposed metal, or sharp protrusions"],
        ["Temperature sensor display (cab)",             "Reading displayed; within 1°C of set-point"],
        ["Data logger – active and recording",           "Check LED indicator; verify start time logged"],
        ["Rear door open/close sensors",                 "Test alert function via FMS app"],
        ["Exterior lighting – refrigeration warning",   "Confirm alarm light functional"],
        ["Fuel/power level for APU",                    "Diesel APU ≥ 75% or shore power confirmed"],
    ]
    story.append(std_table(
        ["Inspection Item", "Pass Criteria"],
        chk_rows,
        col_widths=[2.8*inch, 4.0*inch],
    ))

    story += section("4.  Maintenance Integration")
    story.append(body(
        "Inspection findings must be entered into the Fleet Management System (FMS) within 2 hours "
        "of completion. Any defect generating a FAIL status automatically creates a work order in "
        "the FMS maintenance module and flags the vehicle as 'Out of Service' until resolved. "
        "Refer to SOP-004 for preventive maintenance scheduling requirements."
    ))
    story.append(note(
        "ColdChain Guardian AI monitors open maintenance work orders and will generate an alert if "
        "a vehicle with an unresolved safety-critical work order is assigned to a temperature-sensitive shipment."
    ))

    story += section("5.  Approved Sanitisers (Appendix A)")
    chem_rows = [
        ["Klercide 70/30 IPA",         "70% Isopropyl Alcohol", "RTU",       "Food-contact surfaces (non-porous)"],
        ["Diversey Oxivir TB",          "Hydrogen Peroxide 0.5%","RTU",       "Broad-spectrum; floors and walls"],
        ["Ecolab Sink & Surface Cleaner","Quaternary Ammonium",  "1:128 dilution","Walls, bulkheads; rinse required"],
        ["Diversey Suma Star D1",       "Anionic Surfactant",    "1:200",     "Pre-soak and degreasing step only"],
    ]
    story.append(std_table(
        ["Product Name", "Active Ingredient", "Dilution", "Approved Use"],
        chem_rows,
        col_widths=[1.6*inch, 1.7*inch, 1.1*inch, 2.4*inch],
    ))
    story.append(note(
        "Bleach-based products are NOT approved for refrigerated trailer interiors due to corrosion risk. "
        "Any new sanitiser must be approved by the Food Safety Manager before use."
    ))

    story += section("6.  Revision History")
    story.append(revision_table([
        ["1.0", "2021-06-01", "Initial release",                             "A. Khalil","P. Wells"],
        ["1.5", "2022-09-20", "Added Appendix A approved sanitiser list",    "A. Khalil","P. Wells"],
        ["1.7", "2023-05-10", "Aligned with FSMA Sanitary Transportation final rule update",
         "J. Park",  "P. Wells"],
        ["1.8", "2024-04-01", "Added FMS integration requirements; APU fuel check",
         "A. Khalil","P. Wells"],
    ]))

    doc.build(story)
    return path

# ═════════════════════════════════════════════════════════════════════════════
# SOP-004  Food Safety Incident Reporting and Investigation
# ═════════════════════════════════════════════════════════════════════════════

def build_sop_004():
    path = os.path.join(OUT_DIR, "SOP-004_Incident_Reporting_Investigation.pdf")
    doc  = SopDoc(path, "SOP-004",
                  "Food Safety Incident Reporting and Investigation",
                  "2.0", "2024-10-01")
    story = []

    story += cover_block(
        "SOP-004",
        "Food Safety Incident Reporting and Investigation",
        "HACCP Deviation Management | CAPA | Regulatory Compliance",
        "2.0", "2024-10-01", "2025-10-01",
        "Dr. Patricia Wells, VP Food Safety",
        "Robert Huang, Chief Quality Officer",
    )

    story += section("1.  Purpose")
    story.append(body(
        "This SOP establishes the minimum requirements for identifying, reporting, investigating, and "
        "resolving food safety incidents across all FrostGuard Logistics operations. It ensures that "
        "all incidents are captured in the ColdChain Guardian AI platform for trend analysis, that "
        "root causes are identified and addressed, and that regulatory and customer obligations are met."
    ))

    story += section("2.  Incident Classification Matrix")
    story.append(body(
        "All potential incidents must be classified within 30 minutes of detection using the matrix below. "
        "Classification determines escalation, investigation timeline, and regulatory notification requirements."
    ))
    cls_rows = [
        ["L1 – Low",
         "Minor parameter deviation; corrected without product impact; no regulatory trigger",
         "Supervisor",       "24 hours", "No"],
        ["L2 – Medium",
         "Parameter deviation with potential product quality impact; requires lab testing",
         "Food Safety Manager","48 hours","No (unless distributed)"],
        ["L3 – High",
         "Confirmed product impact; potential public health risk; customer notification required",
         "VP Food Safety",  "5 business days", "Assess with Legal"],
        ["L4 – Critical",
         "Confirmed or probable adulteration; recall potential; imminent public health risk",
         "Executive Team",  "72 hours",  "Mandatory"],
    ]
    story.append(std_table(
        ["Class", "Criteria", "Owner", "Investigation Deadline", "Regulatory Notification"],
        cls_rows,
        col_widths=[0.75*inch, 2.4*inch, 1.0*inch, 1.3*inch, 1.35*inch],
    ))

    story += section("3.  Incident Reporting Procedure")
    story += subsection("3.1  Initial Report (Any Employee)")
    story.append(body(
        "Any FrostGuard employee, driver, or contractor who observes or suspects a food safety incident "
        "MUST report it immediately. There is no threshold below which reporting is optional."
    ))
    for i, s in enumerate([
        "Secure the area, vehicle, or product — do not move or dispose of anything.",
        "Call the 24/7 Incident Hotline: +1-800-555-0199.",
        "Complete the Initial Incident Notification (Form FG-INC-001, Part A) within 1 hour.",
        "Provide: location, product details, lot numbers, time of discovery, and estimated quantity affected.",
        "Do not discuss the incident externally (social media, press, customers) without authorisation from VP Food Safety.",
    ], 1):
        story.append(numbered(i, s))

    story += subsection("3.2  ColdChain Guardian AI Platform Entry")
    story.append(body(
        "All incidents must be logged in the ColdChain Guardian AI platform within 2 hours of initial "
        "report. The AI investigation agent will:"
    ))
    for b in [
        "Cross-reference shipment temperature data, door-event logs, and maintenance records",
        "Calculate the exposure duration and estimate Mean Kinetic Temperature (MKT)",
        "Flag correlated incidents (same truck, driver, route, or refrigeration unit) within the past 90 days",
        "Generate a preliminary Evidence Summary Report for the Food Safety Manager",
        "Recommend classification and disposition based on historical patterns and regulatory thresholds",
    ]:
        story.append(bullet(b))
    story.append(note(
        "AI-generated recommendations are advisory only. Final classification and disposition decisions "
        "must be made and signed by an authorised Food Safety professional."
    ))

    story += section("4.  Investigation Requirements by Class")
    story += subsection("4.1  L3 and L4 Investigation Protocol")
    story.append(body(
        "L3 and L4 incidents require a structured investigation. The following evidence must be "
        "gathered and documented in Form FG-INC-001, Part B:"
    ))
    evid_rows = [
        ["Temperature records",         "Complete data-logger download; all sensor readings from departure to delivery"],
        ["Door event log",              "All door open/close events with timestamps and GPS coordinates"],
        ["Maintenance records",         "Last 2 years of maintenance history for the vehicle involved"],
        ["Driver log / ELD records",    "Hours of service; stops; deviations from planned route"],
        ["Shipper / receiver records",  "Chain of custody; receiving temperature records; customer complaint if applicable"],
        ["Laboratory results",          "Microbiological and chemical testing as directed by Food Safety Manager"],
        ["Photographic evidence",       "Product condition, temperature displays, labels, quarantine area"],
        ["CCTV footage",                "Warehouse or dock footage covering the incident timeframe (if available)"],
    ]
    story.append(std_table(
        ["Evidence Category", "Required Content"],
        evid_rows,
        col_widths=[1.8*inch, 5.0*inch],
    ))

    story += section("5.  Corrective and Preventive Action (CAPA)")
    story.append(body(
        "Every L2–L4 incident must result in a completed CAPA (Form FG-CAPA-001) reviewed and "
        "approved by the VP Food Safety. CAPA effectiveness must be verified within 90 days."
    ))
    capa_rows = [
        ["Immediate correction",   "Stop the hazard; correct the deviation",           "Within 1 hour"],
        ["Containment action",     "Quarantine/recall affected product; notify stakeholders","Within 24 hours"],
        ["Root cause determination","5-Why analysis; fishbone diagram where appropriate","Within investigation deadline"],
        ["Preventive action",      "Systemic change to prevent recurrence",            "Within 30 days of RCA completion"],
        ["Effectiveness check",    "Verify preventive action is working",              "Within 90 days of implementation"],
        ["Trend review",           "Quarterly review of all CAPAs in AI platform",     "Quarterly"],
    ]
    story.append(std_table(
        ["CAPA Stage", "Description", "Timeline"],
        capa_rows,
        col_widths=[1.6*inch, 3.6*inch, 1.6*inch],
    ))

    story += section("6.  Key Performance Indicators (KPIs)")
    story.append(body(
        "The following KPIs are tracked monthly in the ColdChain Guardian AI dashboard. Trends "
        "are reviewed at the monthly Food Safety Committee meeting."
    ))
    kpi_rows = [
        ["Incident Rate",             "Number of incidents per 1,000 shipments",        "< 5 per 1,000"],
        ["Critical Incident Rate",    "Number of L4 incidents per quarter",             "0"],
        ["CAPA Closure Rate",         "% of CAPAs closed within target timeline",       "≥ 95%"],
        ["Regulatory Notifications",  "Number of mandatory regulatory notifications",   "0 per quarter (target)"],
        ["Mean Time to Detect (MTTD)","Avg time from excursion start to detection",     "< 20 minutes"],
        ["Mean Time to Respond (MTTR)","Avg time from detection to Food Safety notification","< 45 minutes"],
        ["Repeat Incidents",          "Same root cause recurring within 180 days",      "0%"],
    ]
    story.append(std_table(
        ["KPI", "Description", "Target"],
        kpi_rows,
        col_widths=[2.0*inch, 3.1*inch, 1.7*inch],
    ))

    story += section("7.  Revision History")
    story.append(revision_table([
        ["1.0", "2022-01-15", "Initial release, replacing legacy FS-INC-003",          "P. Wells",   "R. Huang"],
        ["1.5", "2023-04-01", "Added ColdChain Guardian AI platform requirements §3.2","J. Park",    "P. Wells"],
        ["2.0", "2024-10-01", "Full revision: added L4 class; KPI section; updated regulatory notification matrix",
         "P. Wells",   "R. Huang"],
    ]))

    doc.build(story)
    return path

# ═════════════════════════════════════════════════════════════════════════════
# main
# ═════════════════════════════════════════════════════════════════════════════

def main():
    print("ColdChain Guardian AI – SOP PDF generator")
    print("=" * 50)
    builders = [
        ("SOP-001", "Temperature Monitoring and Control",        build_sop_001),
        ("SOP-002", "Cold Chain Breach Response Protocol",       build_sop_002),
        ("SOP-003", "Vehicle Sanitation and Inspection",         build_sop_003),
        ("SOP-004", "Incident Reporting and Investigation",      build_sop_004),
    ]
    for num, title, fn in builders:
        path = fn()
        size_kb = os.path.getsize(path) // 1024
        print(f"  {num}  {title:<40}  {size_kb:>4} KB  →  {os.path.basename(path)}")
    print("=" * 50)
    print(f"PDFs written to: {OUT_DIR}")

if __name__ == "__main__":
    main()
