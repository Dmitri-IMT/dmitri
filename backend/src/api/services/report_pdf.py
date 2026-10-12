"""PDF rendering for explained scan reports. Technical reports are JSON."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, cast
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Flowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

from api.schemas.ai import AILanguage
from api.schemas.reports import ExplainedReportSections, ScanReportResponse
from api.services.report_education_copy import REPORT_COPY, SCAN_MODES
from api.services.report_education_pdf import EvidenceBars, append_education

# ruff: noqa: E501
_PURPLE = colors.HexColor("#600BB5")
_INK = colors.HexColor("#1F2937")
_MUTED = colors.HexColor("#52606D")
_LIGHT = colors.HexColor("#F5F2F8")
_LINE = colors.HexColor("#DDD6E7")


class ScanReportDocTemplate(SimpleDocTemplate):
    """Clickable PDF navigation for chapters, devices and explained groups."""

    def beforeDocument(self) -> None:
        super().beforeDocument()
        # multiBuild rebuilds the page tree each pass; keep bookmark identifiers
        # stable so TableOfContents can compare its entries and finish.
        self._report_bookmark_index = 0

    def afterFlowable(self, flowable: Any) -> None:
        if not isinstance(flowable, Paragraph):
            return
        title = flowable.getPlainText()
        if title == getattr(self, "contents_label", None):
            return
        chapter = flowable.style.name == "ReportChapter"
        detail = flowable.style.name == "ReportDevice" or (flowable.style.name == "ReportHeading" and re.match(
            r"^(G[0-9]+\s*\||[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+\s*\||"
            r"[0-9]{1,3}(?:\.[0-9]{1,3}){3}\s*\|)", title
        ))
        if not chapter and not detail:
            return
        index = getattr(self, "_report_bookmark_index", 0) + 1
        self._report_bookmark_index = index
        key = f"report-section-{index}"
        self.canv.bookmarkPage(key)
        self.canv.addOutlineEntry(title, key, level=0 if chapter else 1, closed=False)
        self.notify("TOCEntry", (0 if chapter else 1, title, self.page, key))


class CompactTableOfContents(TableOfContents):
    """Roomy, single-column chapter index with readable section spacing."""

    def __init__(self, level_styles, bold_font_name: str, regular_font_name: str):
        super().__init__()
        self.levelStyles = level_styles
        self.bold_font_name = bold_font_name
        self.regular_font_name = regular_font_name

    def wrap(self, avail_width: float, avail_height: float) -> tuple[float, float]:
        entries = self._lastEntries or [(0, "Sumário", 1, None)]
        number_width = 40
        body_width = avail_width - number_width - 12
        rows = []
        for level, title, page, key in entries:
            font_name = self.bold_font_name if level == 0 else self.regular_font_name
            size = 10 if level == 0 else 8.7
            leading = 13 if level == 0 else 11.5
            indent = 0 if level == 0 else 10
            style = ParagraphStyle(
                f"TOCCell{level}", fontName=font_name, fontSize=size,
                leading=leading, textColor=_PURPLE if level == 0 else _INK,
                leftIndent=indent, spaceAfter=0,
            )
            safe_title = escape(title)
            link_color = "#600BB5" if level == 0 else "#1F2937"
            linked_title = (
                f'<link href="#{escape(key)}" color="{link_color}">'
                f"{safe_title}</link>" if key else safe_title
            )
            page_style = ParagraphStyle(
                f"TOCPage{level}", parent=style, leftIndent=0, alignment=TA_RIGHT,
            )
            rows.append([Paragraph(linked_title, style), Paragraph(str(page), page_style)])
        self._table = Table(rows, colWidths=[body_width, number_width], hAlign="LEFT")
        self._table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LINEBELOW", (0, 0), (-1, -1), 0.25, _LINE),
        ]))
        self.width, self.height = self._table.wrap(avail_width, avail_height)
        return self.width, self.height

    def draw(self) -> None:
        self._table.drawOn(self.canv, 0, 0)

    def split(self, avail_width: float, avail_height: float) -> list[Flowable]:
        self.wrap(avail_width, avail_height)
        return self._table.split(avail_width, avail_height)


def render_scan_report_pdf(report: ScanReportResponse) -> bytes:
    if report.kind != "explained":
        raise ValueError("technical reports are downloaded as JSON")
    sections = cast(ExplainedReportSections, report.sections)
    buffer = BytesIO()
    document = ScanReportDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=24 * mm,
        bottomMargin=20 * mm,
        title="Dmitri - explained scan report",
        author="Dmitri",
    )
    styles = getSampleStyleSheet()
    font_name, bold_font_name = _register_unicode_fonts()
    styles.add(ParagraphStyle("ReportHeading", parent=styles["Heading2"], fontName=bold_font_name, fontSize=12, leading=16, textColor=_PURPLE, spaceBefore=11, spaceAfter=5, keepWithNext=True))
    styles.add(ParagraphStyle("ReportChapter", parent=styles["ReportHeading"], fontSize=13, leading=18))
    styles.add(ParagraphStyle("ReportDevice", parent=styles["ReportHeading"]))
    styles.add(ParagraphStyle("ReportBody", parent=styles["BodyText"], fontName=font_name, fontSize=9, leading=13, textColor=_INK, spaceAfter=3))
    styles.add(ParagraphStyle("ReportSmall", parent=styles["BodyText"], fontName=font_name, fontSize=7.5, leading=10, textColor=_MUTED))
    styles.add(ParagraphStyle("ReportCard", parent=styles["BodyText"], fontName=font_name, fontSize=8.5, leading=12, textColor=_INK))
    copy = REPORT_COPY[report.language]
    document.contents_label = copy["contents"]
    devices = sections["devices"]
    appendix = sections["appendix"]
    cover_title = {"en": "Explained report", "pt-BR": "Relatório explicado", "ru": "Понятный отчёт"}[report.language]
    hero = Table(
        [[Paragraph("Dmitri", ParagraphStyle("CoverBrand", fontName=bold_font_name, fontSize=12, leading=16, textColor=colors.HexColor("#E7D8FA")))],
         [Paragraph(cover_title, ParagraphStyle("CoverTitle", fontName=bold_font_name, fontSize=26, leading=32, textColor=colors.white))]],
        colWidths=[document.width],
    )
    hero.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _PURPLE),
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("LEFTPADDING", (0, 0), (-1, -1), 18),
        ("RIGHTPADDING", (0, 0), (-1, -1), 18),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 16),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 18),
    ]))
    cover_metrics = [
        (copy["hosts"], len(devices)),
        (copy["findings"], len(appendix)),
        (copy["cves"], len({item["reference"] for item in appendix if item["reference"]})),
        (copy["ports"], sum(device["open_ports"] for device in devices)),
    ]
    metric_cells = [[Paragraph(
        f'<font color="#600BB5" size="20"><b>{escape(str(value))}</b></font><br/>'
        f'<font color="#52606D" size="8">{escape(label)}</font>',
        ParagraphStyle("CoverMetric", fontName=font_name, fontSize=8, leading=12, alignment=1),
    ) for label, value in cover_metrics]]
    metric_table = Table(metric_cells, colWidths=[document.width / 4] * 4)
    metric_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.6, _LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, _LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    metadata = Table([
        [Paragraph(f"<b>{escape(copy['scan_timestamp'])}</b>", styles["ReportCard"]),
         Paragraph(escape(_format_timestamp(sections["scan_timestamp"])), styles["ReportCard"])],
        [Paragraph(f"<b>{escape(copy['scope'])}</b>", styles["ReportCard"]),
         Paragraph(escape(_clean_text(sections["scope"])), styles["ReportCard"])],
        [Paragraph(f"<b>{escape(copy['mode'])}</b>", styles["ReportCard"]),
         Paragraph(escape(_scan_mode_label(sections["scan_mode"], report.language)), styles["ReportCard"])],
        [Paragraph(f"<b>{escape(copy['generated'])}</b>", styles["ReportCard"]),
         Paragraph(escape(_clean_text(report.generated_at.strftime("%d/%m/%Y %H:%M UTC"))), styles["ReportCard"])],
    ], colWidths=[42 * mm, document.width - 42 * mm])
    metadata.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.35, _LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    top_devices = sorted(devices, key=lambda device: (-device["finding_count"], device["address"]))[:3]
    story: list[Any] = [
        hero,
        Spacer(1, 9 * mm),
        Paragraph(copy["intro"], styles["ReportBody"]),
        Spacer(1, 5 * mm),
        Paragraph(copy["overview"], styles["ReportHeading"]),
        Paragraph(escape(_clean_text(sections["overview"])), styles["ReportBody"]),
        Spacer(1, 7 * mm),
        metric_table,
        Paragraph(copy["hosts_chart"], styles["ReportHeading"]),
        EvidenceBars(
            [(device["display_name"] + "\n" + device["address"], [device["finding_count"]])
             for device in top_devices],
            [copy["findings"]], ["#600BB5"], document.width - 12, font_name,
        ),
        Spacer(1, 8 * mm),
        metadata,
        Spacer(1, 5 * mm),
        Paragraph(f"ID: {escape(str(report.scan_id))}", styles["ReportSmall"]),
    ]
    toc_styles = [
        ParagraphStyle(
            "TOCChapter", fontName=bold_font_name, fontSize=10, leading=14,
            textColor=_PURPLE, leftIndent=0, firstLineIndent=0, spaceBefore=3,
        ),
        ParagraphStyle(
            "TOCDetail", fontName=font_name, fontSize=7.2, leading=8.4,
            textColor=_INK, leftIndent=5, firstLineIndent=0, spaceBefore=0,
        ),
    ]
    contents = CompactTableOfContents(toc_styles, bold_font_name, font_name)
    story.extend([
        PageBreak(),
        Paragraph(copy["contents"], styles["ReportChapter"]),
        contents,
        PageBreak(),
    ])
    append_education(story, sections, styles, copy, report.language, document.width, font_name)
    document.multiBuild(
        story,
        onFirstPage=lambda canvas, doc: _page_chrome(canvas, doc, copy, report),
        onLaterPages=lambda canvas, doc: _page_chrome(canvas, doc, copy, report),
    )
    return buffer.getvalue()


def _page_chrome(canvas: Any, document: Any, copy: dict[str, str], report: ScanReportResponse) -> None:
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(_LINE)
    canvas.setLineWidth(0.6)
    canvas.line(document.leftMargin, height - 15 * mm, width - document.rightMargin, height - 15 * mm)
    canvas.line(document.leftMargin, 13 * mm, width - document.rightMargin, 13 * mm)
    canvas.setFont("DmitriUnicode", 7.5)
    canvas.setFillColor(_MUTED)
    canvas.drawString(document.leftMargin, 8.5 * mm, f"Dmitri | {report.scan_id}")
    canvas.drawRightString(width - document.rightMargin, 8.5 * mm, f"{copy['page']} {document.page}")
    canvas.restoreState()


def _scan_mode_label(mode: object, language: AILanguage) -> str:
    normalized = _clean_text(mode).casefold()
    return SCAN_MODES[language].get(normalized, normalized or "-")


def _format_timestamp(value: object) -> str:
    if isinstance(value, datetime):
        return _clean_text(value.strftime("%d/%m/%Y %H:%M UTC"))
    if value:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return _clean_text(value)
        return _clean_text(parsed.strftime("%d/%m/%Y %H:%M UTC"))
    return "-"


def _register_unicode_fonts() -> tuple[str, str]:
    candidates = (
        (Path("/System/Library/Fonts/Supplemental/Arial.ttf"), Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf")),
        (Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")),
        (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
        (Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"), Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf")),
    )
    for regular_path, bold_path in candidates:
        if regular_path.exists() and bold_path.exists():
            if "DmitriUnicode" not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont("DmitriUnicode", str(regular_path)))
                pdfmetrics.registerFont(TTFont("DmitriUnicode-Bold", str(bold_path)))
                pdfmetrics.registerFontFamily("DmitriUnicode", normal="DmitriUnicode", bold="DmitriUnicode-Bold")
            return "DmitriUnicode", "DmitriUnicode-Bold"
    raise RuntimeError("A Unicode font is required to render scan reports. Install Arial, DejaVu Sans, or Liberation Sans on the report worker.")


def _clean_text(value: object) -> str:
    text = str(value or "")
    text = text.replace("\u2010", "-").replace("\u2011", "-").replace("\u2012", "-").replace("\u2013", "-").replace("\u2014", "-").replace("\u2212", "-").replace("\u2022", "-")
    text = text.replace("\u2018", "'").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    return unicodedata.normalize("NFC", text)
