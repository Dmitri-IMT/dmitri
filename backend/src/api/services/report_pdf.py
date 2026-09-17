from __future__ import annotations

import json
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
)

from api.schemas.reports import ScanReportResponse


def render_scan_report_pdf(report: ScanReportResponse) -> bytes:
    """Render the user-facing report as a readable, static PDF."""
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Dmitri - {report.kind} scan report",
        author="Dmitri",
    )
    styles = getSampleStyleSheet()
    styles["Title"].alignment = TA_CENTER
    styles["Title"].textColor = "#16324F"
    styles["Heading2"].textColor = "#16324F"
    styles["BodyText"].leading = 15
    styles.add(
        styles["BodyText"].clone(
            "ReportMeta", fontSize=9, textColor="#52606D", leading=11
        )
    )

    story: list[Any] = [
        Paragraph("Dmitri", styles["Title"]),
        Paragraph(
            "Relatório explicado"
            if report.kind == "explained"
            else "Relatório técnico",
            styles["Heading2"],
        ),
        Paragraph(
            f"Scan: {escape(str(report.scan_id))}<br/>"
            f"Gerado em: {escape(report.generated_at.isoformat())}",
            styles["ReportMeta"],
        ),
        Spacer(1, 10),
    ]

    if report.kind == "explained":
        _append_explained(story, report.sections, styles)
    else:
        _append_technical(story, report.sections, styles)

    document.build(story)
    return buffer.getvalue()


def _append_explained(story: list[Any], sections: dict[str, Any], styles: Any) -> None:
    _append_text_section(story, "O que encontramos", sections.get("overview"), styles)
    _append_text_section(
        story,
        "Nível de atenção",
        str(sections.get("attention_level", "unknown")).capitalize(),
        styles,
    )
    story.append(Paragraph("O que fazer primeiro", styles["Heading2"]))
    for action in sections.get("what_to_do_first", []):
        if isinstance(action, dict):
            title = action.get("title") or action.get("action") or "Ação recomendada"
            detail = action.get("explanation") or action.get("description") or ""
            text = f"<b>{escape(str(title))}</b>: {escape(str(detail))}"
        else:
            text = escape(str(action))
        story.append(Paragraph(f"- {text}", styles["BodyText"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph("Limitações e incertezas", styles["Heading2"]))
    for limitation in sections.get("limitations", []):
        story.append(Paragraph(f"- {escape(str(limitation))}", styles["BodyText"]))


def _append_technical(story: list[Any], sections: dict[str, Any], styles: Any) -> None:
    story.append(Paragraph("Dados completos do scan", styles["Heading2"]))
    story.append(
        Preformatted(
            _pretty_json(sections.get("scan")),
            styles["Code"],
            maxLineLength=100,
        )
    )
    story.append(PageBreak())
    story.append(Paragraph("Resumo de risco", styles["Heading2"]))
    story.append(
        Preformatted(
            _pretty_json(sections.get("risk_summary")),
            styles["Code"],
            maxLineLength=100,
        )
    )
    story.append(Spacer(1, 10))
    story.append(Paragraph("Análise da IA", styles["Heading2"]))
    story.append(
        Preformatted(
            _pretty_json(sections.get("ai_analysis")),
            styles["Code"],
            maxLineLength=100,
        )
    )


def _append_text_section(
    story: list[Any], title: str, value: object, styles: Any
) -> None:
    story.append(Paragraph(escape(title), styles["Heading2"]))
    story.append(Paragraph(escape(str(value or "Não informado.")), styles["BodyText"]))
    story.append(Spacer(1, 8))


def _pretty_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, indent=2, default=str)
