"""PDF rendering for user-facing and technical scan reports."""

# The long Portuguese copy is intentionally kept together for translation review.
# ruff: noqa: E501
from __future__ import annotations

import json
import unicodedata
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
    """Render an accessible explained PDF or a complete technical PDF."""
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
    styles["Title"].textColor = "#600BB5"
    styles["Heading2"].textColor = "#600BB5"
    styles["BodyText"].leading = 15
    styles.add(styles["BodyText"].clone("ReportMeta", fontSize=9, textColor="#52606D", leading=11))
    title = "Relat\u00f3rio explicado" if report.kind == "explained" else "Relat\u00f3rio t\u00e9cnico"
    story: list[Any] = [
        Paragraph("Dmitri", styles["Title"]),
        Paragraph(title, styles["Heading2"]),
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
    story.append(
        Paragraph(
            "Este resumo traduz os resultados da varredura para uma linguagem simples. "
            "Ele indica o que merece aten\u00e7\u00e3o e quais a\u00e7\u00f5es devem ser priorizadas.",
            styles["BodyText"],
        )
    )
    story.append(Spacer(1, 10))
    _append_text_section(story, "O que encontramos", sections.get("overview"), styles)
    level = str(sections.get("attention_level", "unknown"))
    _append_text_section(story, "N\u00edvel de aten\u00e7\u00e3o", _attention_label(level), styles)
    story.append(Paragraph("Como interpretar este resultado", styles["Heading2"]))
    story.append(Paragraph(_attention_guidance(level), styles["BodyText"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph("O que fazer primeiro", styles["Heading2"]))
    for action in sections.get("what_to_do_first", []):
        if isinstance(action, dict):
            title = action.get("title") or action.get("action") or "A\u00e7\u00e3o recomendada"
            detail = action.get("explanation") or action.get("description") or ""
            text = f"<b>{escape(_clean_text(title))}</b>: {escape(_clean_text(detail))}"
        else:
            text = escape(_clean_text(action))
        story.append(Paragraph(f"- {text}", styles["BodyText"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph("O que ainda n\u00e3o podemos afirmar", styles["Heading2"]))
    for limitation in sections.get("limitations", []):
        story.append(
            Paragraph(f"- {escape(_clean_text(limitation))}", styles["BodyText"])
        )
    story.append(Spacer(1, 8))
    story.append(Paragraph("Pr\u00f3ximo passo", styles["Heading2"]))
    story.append(Paragraph(
        "Use esta lista para corrigir os itens priorit\u00e1rios. Se precisar de detalhes "
        "t\u00e9cnicos ou de valida\u00e7\u00e3o profissional, encaminhe tamb\u00e9m o relat\u00f3rio t\u00e9cnico.",
        styles["BodyText"],
    ))


def _append_technical(story: list[Any], sections: dict[str, Any], styles: Any) -> None:
    story.append(Paragraph("Dados completos do scan", styles["Heading2"]))
    story.append(Preformatted(_pretty_json(sections.get("scan")), styles["Code"], maxLineLength=100))
    story.append(PageBreak())
    story.append(Paragraph("Resumo de risco", styles["Heading2"]))
    story.append(Preformatted(_pretty_json(sections.get("risk_summary")), styles["Code"], maxLineLength=100))
    story.append(Spacer(1, 10))
    story.append(Paragraph("An\u00e1lise da IA", styles["Heading2"]))
    story.append(Preformatted(_pretty_json(sections.get("ai_analysis")), styles["Code"], maxLineLength=100))


def _append_text_section(story: list[Any], title: str, value: object, styles: Any) -> None:
    story.append(Paragraph(escape(_clean_text(title)), styles["Heading2"]))
    story.append(
        Paragraph(
            escape(_clean_text(value or "N\u00e3o informado.")), styles["BodyText"]
        )
    )
    story.append(Spacer(1, 8))


def _attention_label(level: str) -> str:
    return {
        "critical": "Aten\u00e7\u00e3o m\u00e1xima",
        "high": "Aten\u00e7\u00e3o alta",
        "medium": "Aten\u00e7\u00e3o moderada",
        "low": "Pouca aten\u00e7\u00e3o necess\u00e1ria",
        "none": "Nenhum problema cr\u00edtico identificado",
    }.get(level, "N\u00edvel n\u00e3o confirmado")


def _attention_guidance(level: str) -> str:
    return {
        "critical": (
            "Existem problemas que devem ser tratados imediatamente, principalmente "
            "os que podem permitir acesso indevido ou comprometer dados."
        ),
        "high": (
            "Existem problemas importantes. Planeje as corre\u00e7\u00f5es com prioridade "
            "e evite deixar esses servi\u00e7os expostos sem necessidade."
        ),
        "medium": (
            "Existem melhorias recomendadas. Corrija os itens mais graves e acompanhe "
            "os demais em uma pr\u00f3xima revis\u00e3o."
        ),
        "low": (
            "Foram identificados poucos sinais de risco. Mantenha as atualiza\u00e7\u00f5es "
            "e revise os itens listados quando poss\u00edvel."
        ),
        "none": (
            "A varredura n\u00e3o encontrou problemas cr\u00edticos, mas isso n\u00e3o "
            "substitui atualiza\u00e7\u00f5es e boas pr\u00e1ticas de seguran\u00e7\u00e3a."
        ),
    }.get(
        level,
        "O n\u00edvel de aten\u00e7\u00e3o n\u00e3o p\u00f4de ser confirmado com os dados dispon\u00edveis.",
    )


def _pretty_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, indent=2, default=str)


def _clean_text(value: object) -> str:
    """Keep PDF text readable when the model returns typographic punctuation."""
    text = str(value).replace("\u2010", "-")
    text = text.replace("\u2011", "-").replace("\u2012", "-")
    text = text.replace("\u2013", "-").replace("\u2014", "-")
    text = text.replace("\u2212", "-").replace("\u2022", "-")
    text = text.replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    return unicodedata.normalize("NFC", text)
