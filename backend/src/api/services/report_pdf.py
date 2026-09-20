"""PDF rendering for user-facing and technical scan reports."""

from __future__ import annotations

# Translation tables and PDF layout strings intentionally remain readable together.
# ruff: noqa: E501
import json
import unicodedata
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
)

from api.schemas.ai import AILanguage
from api.schemas.reports import ScanReportResponse

_COPY: dict[AILanguage, dict[str, str]] = {
    "en": {"explained": "Explained report", "technical": "Technical report", "generated": "Generated at", "intro": "This summary translates the scan results into plain language.", "overview": "What we found", "attention": "Attention level", "interpret": "How to interpret this result", "first": "What to do first", "limitations": "What we cannot confirm yet", "next": "Next step", "next_body": "Use this list to address the priority items. For technical details, also share the technical report.", "technical_data": "Complete scan data", "risk": "Risk summary", "ai": "AI analysis"},
    "pt-BR": {"explained": "Relat\u00f3rio explicado", "technical": "Relat\u00f3rio t\u00e9cnico", "generated": "Gerado em", "intro": "Este resumo traduz os resultados da varredura para uma linguagem simples.", "overview": "O que encontramos", "attention": "N\u00edvel de aten\u00e7\u00e3o", "interpret": "Como interpretar este resultado", "first": "O que fazer primeiro", "limitations": "O que ainda n\u00e3o podemos afirmar", "next": "Pr\u00f3ximo passo", "next_body": "Use esta lista para corrigir os itens priorit\u00e1rios. Para detalhes t\u00e9cnicos, consulte tamb\u00e9m o relat\u00f3rio t\u00e9cnico.", "technical_data": "Dados completos do scan", "risk": "Resumo de risco", "ai": "An\u00e1lise da IA"},
    "ru": {"explained": "\u041f\u043e\u043d\u044f\u0442\u043d\u044b\u0439 \u043e\u0442\u0447\u0451\u0442", "technical": "\u0422\u0435\u0445\u043d\u0438\u0447\u0435\u0441\u043a\u0438\u0439 \u043e\u0442\u0447\u0451\u0442", "generated": "\u0421\u043e\u0437\u0434\u0430\u043d", "intro": "\u042d\u0442\u043e \u043a\u0440\u0430\u0442\u043a\u043e\u0435 \u043e\u043f\u0438\u0441\u0430\u043d\u0438\u0435 \u0440\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442\u043e\u0432 \u0441\u043a\u0430\u043d\u0438\u0440\u043e\u0432\u0430\u043d\u0438\u044f \u043f\u0440\u043e\u0441\u0442\u044b\u043c \u044f\u0437\u044b\u043a\u043e\u043c.", "overview": "\u0427\u0442\u043e \u043e\u0431\u043d\u0430\u0440\u0443\u0436\u0435\u043d\u043e", "attention": "\u0423\u0440\u043e\u0432\u0435\u043d\u044c \u0432\u043d\u0438\u043c\u0430\u043d\u0438\u044f", "interpret": "\u041a\u0430\u043a \u043f\u043e\u043d\u0438\u043c\u0430\u0442\u044c \u0440\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442", "first": "\u0427\u0442\u043e \u0441\u0434\u0435\u043b\u0430\u0442\u044c \u0432 \u043f\u0435\u0440\u0432\u0443\u044e \u043e\u0447\u0435\u0440\u0435\u0434\u044c", "limitations": "\u0427\u0442\u043e \u043f\u043e\u043a\u0430 \u043d\u0435\u043b\u044c\u0437\u044f \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0434\u0438\u0442\u044c", "next": "\u0421\u043b\u0435\u0434\u0443\u044e\u0449\u0438\u0439 \u0448\u0430\u0433", "next_body": "\u0418\u0441\u043f\u043e\u043b\u044c\u0437\u0443\u0439\u0442\u0435 \u0441\u043f\u0438\u0441\u043e\u043a \u0434\u043b\u044f \u0443\u0441\u0442\u0440\u0430\u043d\u0435\u043d\u0438\u044f \u043f\u0440\u0438\u043e\u0440\u0438\u0442\u0435\u0442\u043d\u044b\u0445 \u043f\u0440\u043e\u0431\u043b\u0435\u043c. \u0414\u043b\u044f \u0442\u0435\u0445\u043d\u0438\u0447\u0435\u0441\u043a\u0438\u0445 \u0434\u0435\u0442\u0430\u043b\u0435\u0439 \u0442\u0430\u043a\u0436\u0435 \u043f\u0435\u0440\u0435\u0434\u0430\u0439\u0442\u0435 \u0442\u0435\u0445\u043d\u0438\u0447\u0435\u0441\u043a\u0438\u0439 \u043e\u0442\u0447\u0451\u0442.", "technical_data": "\u041f\u043e\u043b\u043d\u044b\u0435 \u0434\u0430\u043d\u043d\u044b\u0435 \u0441\u043a\u0430\u043d\u0438\u0440\u043e\u0432\u0430\u043d\u0438\u044f", "risk": "\u0421\u0432\u043e\u0434\u043a\u0430 \u0440\u0438\u0441\u043a\u043e\u0432", "ai": "\u0410\u043d\u0430\u043b\u0438\u0437 \u0418\u0418"},
}

_LEVELS = {
    "critical": {"en": "Critical", "pt-BR": "Aten\u00e7\u00e3o m\u00e1xima", "ru": "\u041a\u0440\u0438\u0442\u0438\u0447\u0435\u0441\u043a\u0438\u0439"},
    "high": {"en": "High", "pt-BR": "Aten\u00e7\u00e3o alta", "ru": "\u0412\u044b\u0441\u043e\u043a\u0438\u0439"},
    "medium": {"en": "Moderate", "pt-BR": "Aten\u00e7\u00e3o moderada", "ru": "\u0421\u0440\u0435\u0434\u043d\u0438\u0439"},
    "low": {"en": "Low", "pt-BR": "Pouca aten\u00e7\u00e3o necess\u00e1ria", "ru": "\u041d\u0438\u0437\u043a\u0438\u0439"},
    "none": {"en": "No critical issue identified", "pt-BR": "Nenhum problema cr\u00edtico identificado", "ru": "\u041a\u0440\u0438\u0442\u0438\u0447\u0435\u0441\u043a\u0438\u0445 \u043f\u0440\u043e\u0431\u043b\u0435\u043c \u043d\u0435 \u043e\u0431\u043d\u0430\u0440\u0443\u0436\u0435\u043d\u043e"},
}


def render_scan_report_pdf(report: ScanReportResponse) -> bytes:
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=18 * mm, bottomMargin=18 * mm, title=f"Dmitri - {report.kind} scan report", author="Dmitri")
    styles = getSampleStyleSheet()
    styles["Title"].alignment = TA_CENTER
    styles["Title"].textColor = "#600BB5"
    styles["Heading2"].textColor = "#600BB5"
    styles["BodyText"].leading = 15
    styles.add(styles["BodyText"].clone("ReportMeta", fontSize=9, textColor="#52606D", leading=11))
    font_name, bold_font_name = _register_unicode_fonts()
    for style_name in ("Title", "Heading2", "BodyText", "ReportMeta", "Code"):
        styles[style_name].fontName = bold_font_name if style_name in {"Title", "Heading2"} else font_name
    copy = _COPY[report.language]
    story: list[Any] = [Paragraph("Dmitri", styles["Title"]), Paragraph(copy[report.kind], styles["Heading2"]), Paragraph(f"Scan: {escape(str(report.scan_id))}<br/>{copy['generated']}: {escape(report.generated_at.isoformat())}", styles["ReportMeta"]), Spacer(1, 10)]
    if report.kind == "explained":
        _append_explained(story, report.sections, styles, copy, report.language)
    else:
        _append_technical(story, report.sections, styles, copy)
    document.build(story)
    return buffer.getvalue()


def _register_unicode_fonts() -> tuple[str, str]:
    candidates = (
        (Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")),
        (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
        (Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"), Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf")),
    )
    for regular_path, bold_path in candidates:
        if regular_path.exists() and bold_path.exists():
            if "DmitriUnicode" not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont("DmitriUnicode", str(regular_path)))
                pdfmetrics.registerFont(TTFont("DmitriUnicode-Bold", str(bold_path)))
            return "DmitriUnicode", "DmitriUnicode-Bold"
    raise RuntimeError(
        "A Unicode font is required to render scan reports. "
        "Install Arial, DejaVu Sans, or Liberation Sans on the report worker."
    )


def _append_explained(story: list[Any], sections: dict[str, Any], styles: Any, copy: dict[str, str], language: AILanguage) -> None:
    story.extend([Paragraph(copy["intro"], styles["BodyText"]), Spacer(1, 10)])
    _append_text_section(story, copy["overview"], sections.get("overview"), styles)
    level = str(sections.get("attention_level", "unknown"))
    _append_text_section(story, copy["attention"], _LEVELS.get(level, {}).get(language, "Unconfirmed level"), styles)
    story.extend([Paragraph(copy["interpret"], styles["Heading2"]), Paragraph(_attention_guidance(level, language), styles["BodyText"]), Spacer(1, 8), Paragraph(copy["first"], styles["Heading2"])])
    for action in sections.get("what_to_do_first", []):
        if isinstance(action, dict):
            title = action.get("title") or action.get("action") or "Recommended action"
            detail = action.get("explanation") or action.get("description") or ""
            text = f"<b>{escape(_clean_text(title))}</b>: {escape(_clean_text(detail))}"
        else:
            text = escape(_clean_text(action))
        story.append(Paragraph(f"- {text}", styles["BodyText"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph(copy["limitations"], styles["Heading2"]))
    for limitation in sections.get("limitations", []):
        story.append(Paragraph(f"- {escape(_clean_text(limitation))}", styles["BodyText"]))
    story.extend([Spacer(1, 8), Paragraph(copy["next"], styles["Heading2"]), Paragraph(copy["next_body"], styles["BodyText"])])


def _append_technical(story: list[Any], sections: dict[str, Any], styles: Any, copy: dict[str, str]) -> None:
    story.extend([Paragraph(copy["technical_data"], styles["Heading2"]), Preformatted(_pretty_json(sections.get("scan")), styles["Code"], maxLineLength=100), PageBreak(), Paragraph(copy["risk"], styles["Heading2"]), Preformatted(_pretty_json(sections.get("risk_summary")), styles["Code"], maxLineLength=100), Spacer(1, 10), Paragraph(copy["ai"], styles["Heading2"]), Preformatted(_pretty_json(sections.get("ai_analysis")), styles["Code"], maxLineLength=100)])


def _append_text_section(story: list[Any], title: str, value: object, styles: Any) -> None:
    story.extend([Paragraph(escape(_clean_text(title)), styles["Heading2"]), Paragraph(escape(_clean_text(value or "Not provided.")), styles["BodyText"]), Spacer(1, 8)])


def _attention_guidance(level: str, language: AILanguage) -> str:
    texts = {
        "critical": {"en": "Some problems should be addressed immediately, especially those that may allow unauthorized access or compromise data.", "pt-BR": "Alguns problemas devem ser tratados imediatamente, principalmente os que podem permitir acesso indevido ou comprometer dados.", "ru": "Некоторые проблемы нужно устранить немедленно, особенно те, которые могут привести к несанкционированному доступу или утечке данных."},
        "high": {"en": "Important problems were identified. Plan corrections with priority and avoid unnecessary exposure.", "pt-BR": "Foram identificados problemas importantes. Planeje as correções com prioridade e evite exposição desnecessária.", "ru": "Обнаружены важные проблемы. Запланируйте их устранение в приоритетном порядке и избегайте ненужной открытости сервисов."},
        "medium": {"en": "Recommended improvements were identified. Fix the most serious items and review the rest later.", "pt-BR": "Foram identificadas melhorias recomendadas. Corrija os itens mais graves e revise os demais depois.", "ru": "Обнаружены рекомендуемые улучшения. Исправьте наиболее серьёзные проблемы и позже проверьте остальные."},
        "low": {"en": "Few risk signals were identified. Keep systems updated and review the listed items when possible.", "pt-BR": "Foram identificados poucos sinais de risco. Mantenha os sistemas atualizados e revise os itens quando possível.", "ru": "Обнаружено мало признаков риска. Поддерживайте системы в актуальном состоянии и проверьте перечисленные пункты."},
        "none": {"en": "No critical problems were found, but this does not replace updates and good security practices.", "pt-BR": "Nenhum problema crítico foi encontrado, mas isso não substitui atualizações e boas práticas de segurança.", "ru": "Критических проблем не обнаружено, но это не заменяет обновления и хорошие методы защиты."},
    }
    return texts.get(level, {"en": "The attention level could not be confirmed from the available data.", "pt-BR": "O nível de atenção não pôde ser confirmado com os dados disponíveis.", "ru": "Уровень внимания не удалось подтвердить по доступным данным."})[language]


def _pretty_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, indent=2, default=str)


def _clean_text(value: object) -> str:
    text = str(value).replace("\u2010", "-").replace("\u2011", "-").replace("\u2012", "-").replace("\u2013", "-").replace("\u2014", "-").replace("\u2212", "-").replace("\u2022", "-")
    text = text.replace("\u2018", "'").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    return unicodedata.normalize("NFC", text)
