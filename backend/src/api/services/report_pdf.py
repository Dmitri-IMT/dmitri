"""PDF rendering for user-facing and technical scan reports."""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

from api.schemas.ai import AILanguage
from api.schemas.reports import ScanReportResponse
from api.services.report_education_pdf import append_education

# ruff: noqa: E501
_COPY: dict[AILanguage, dict[str, str]] = {
    "en": {
        "explained": "Network scan report", "technical": "Technical report", "generated": "Generated",
        "intro": "A clear summary of the devices and security observations returned by this scan.",
        "overview": "Executive summary", "attention": "Attention level", "interpret": "What this means",
        "first": "Recommended priorities", "limitations": "What this scan cannot confirm", "next": "Next step",
        "next_body": "Use these findings to plan improvements. Ask an IT professional for help with changes you are unsure about.",
        "technical_data": "Complete scan data", "risk": "Risk summary", "ai": "AI analysis",
        "hosts": "Devices seen", "findings": "Finding records", "cves": "Distinct CVE IDs", "ports": "Open ports",
        "scan_timestamp": "Scan date and time", "scope": "Scan scope", "mode": "Scan type",
        "severity_chart": "Findings by technical severity", "severity_note": "Bars compare finding records by category. Severity describes each issue, not the risk of the whole network.",
        "hosts_chart": "Devices with the most findings", "details": "Important findings", "method": "How the scan works",
        "address": "Address", "service": "Observed service", "severity": "Severity", "cvss": "CVSS technical severity (0-10)",
        "description": "What was observed", "why": "Why it may matter", "recommendation": "Recommended action",
        "evidence": "Evidence recorded by the scan", "uncertainty": "Note", "no_findings": "No finding records were returned by this scan.",
        "no_hosts": "No devices with findings were listed.", "none": "No finding records were returned. This does not prove the network is free of security issues.",
        "high": "High attention", "critical": "Immediate attention", "medium": "Review recommended", "low": "Routine review", "default": "Unable to determine",
        "level_none": "No finding records returned",
        "contents": "Contents",
        "page": "Page", "assessment_unavailable": "Device exposure assessment was unavailable.",
    },
    "pt-BR": {
        "explained": "Relatório da varredura de rede", "technical": "Relatório técnico", "generated": "Gerado em",
        "intro": "Um resumo claro dos equipamentos e dos pontos de segurança observados nesta varredura.",
        "overview": "Resumo executivo", "attention": "Nível de atenção", "interpret": "O que isso significa",
        "first": "Prioridades recomendadas", "limitations": "O que esta varredura não confirma", "next": "Próximo passo",
        "next_body": "Use estes achados para planejar melhorias. Peça ajuda a um profissional de TI para mudanças sobre as quais tiver dúvida.",
        "technical_data": "Dados completos da varredura", "risk": "Resumo de risco", "ai": "Análise da IA",
        "hosts": "Equipamentos encontrados", "findings": "Registros de achados", "cves": "Identificadores CVE distintos", "ports": "Portas abertas",
        "scan_timestamp": "Data e hora da varredura", "scope": "Escopo da varredura", "mode": "Tipo de varredura",
        "severity_chart": "Achados por gravidade técnica", "severity_note": "As barras comparam registros de achados por categoria. A gravidade descreve cada problema, não o risco de toda a rede.",
        "hosts_chart": "Equipamentos com mais achados", "details": "Achados importantes", "method": "Como a varredura funciona",
        "address": "Endereço", "service": "Serviço observado", "severity": "Gravidade", "cvss": "Gravidade técnica CVSS (0-10)",
        "description": "O que foi observado", "why": "Por que isso pode importar", "recommendation": "Ação recomendada",
        "evidence": "Evidência registrada pela varredura", "uncertainty": "Observação", "no_findings": "Esta varredura não retornou registros de achados.",
        "no_hosts": "Nenhum equipamento com achados foi listado.", "none": "A varredura não retornou registros de achados. Isso não comprova que a rede esteja livre de problemas de segurança.",
        "high": "Atenção alta", "critical": "Atenção imediata", "medium": "Revisão recomendada", "low": "Revisão de rotina", "default": "Não foi possível determinar",
        "level_none": "Nenhum registro de achado retornado",
        "contents": "Sumário",
        "page": "Página", "assessment_unavailable": "A avaliação de exposição dos equipamentos não estava disponível.",
    },
    "ru": {
        "explained": "Отчёт о сканировании сети", "technical": "Технический отчёт", "generated": "Создан",
        "intro": "Понятная сводка устройств и замечаний безопасности, обнаруженных при сканировании.",
        "overview": "Краткий итог", "attention": "Уровень внимания", "interpret": "Что это значит",
        "first": "Рекомендуемые приоритеты", "limitations": "Что это сканирование не подтверждает", "next": "Следующий шаг",
        "next_body": "Используйте эти находки для планирования улучшений. Обратитесь к специалисту по ИТ, если не уверены в изменениях.",
        "technical_data": "Полные данные сканирования", "risk": "Сводка рисков", "ai": "Анализ ИИ",
        "hosts": "Обнаружено устройств", "findings": "Записи о находках", "cves": "Различные идентификаторы CVE", "ports": "Открытые порты",
        "scan_timestamp": "Дата и время сканирования", "scope": "Область сканирования", "mode": "Тип сканирования",
        "severity_chart": "Находки по технической серьёзности", "severity_note": "Столбцы сравнивают записи по категориям. Серьёзность описывает проблему, а не общий риск сети.",
        "hosts_chart": "Устройства с наибольшим числом находок", "details": "Важные находки", "method": "Как работает сканирование",
        "address": "Адрес", "service": "Обнаруженная служба", "severity": "Серьёзность", "cvss": "Техническая серьёзность CVSS (0-10)",
        "description": "Что обнаружено", "why": "Почему это может быть важно", "recommendation": "Рекомендуемое действие",
        "evidence": "Данные сканирования", "uncertainty": "Примечание", "no_findings": "Сканирование не вернуло записей о находках.",
        "no_hosts": "Устройства с находками не указаны.", "none": "Сканирование не вернуло записей о находках. Это не доказывает отсутствие проблем безопасности в сети.",
        "high": "Высокий уровень внимания", "critical": "Требуется срочное внимание", "medium": "Рекомендуется проверка", "low": "Плановая проверка", "default": "Не удалось определить",
        "level_none": "Записи о находках не получены",
        "contents": "Содержание",
        "page": "Страница", "assessment_unavailable": "Оценка открытых служб устройств недоступна.",
    },
}

_SCAN_MODES: dict[AILanguage, dict[str, str]] = {
    "en": {
        "quick": "Quick (basic port checks)",
        "standard": "Standard (common services)",
        "extensive": "Extensive (more ports and encryption checks)",
        "max": "Max (all ports)",
        "nspi": "NSPi (industrial and Windows remote access services)",
    },
    "pt-BR": {
        "quick": "Rápida (verificação básica de portas)",
        "standard": "Padrão (serviços comuns)",
        "extensive": "Extensiva (mais portas e verificações de criptografia)",
        "max": "Máxima (todas as portas)",
        "nspi": "NSPi (serviços industriais e acesso remoto do Windows)",
    },
    "ru": {
        "quick": "Быстрое (базовая проверка портов)",
        "standard": "Стандартное (распространённые службы)",
        "extensive": "Расширенное (больше портов и проверка шифрования)",
        "max": "Максимальное (все порты)",
        "nspi": "NSPi (промышленные службы и удалённый доступ Windows)",
    },
}

_SEVERITY = {
    "critical": {"en": "Critical", "pt-BR": "Crítica", "ru": "Критическая"},
    "high": {"en": "High", "pt-BR": "Alta", "ru": "Высокая"},
    "medium": {"en": "Medium", "pt-BR": "Moderada", "ru": "Средняя"},
    "low": {"en": "Low", "pt-BR": "Baixa", "ru": "Низкая"},
}
_LEVELS = {
    "critical": {"en": "Address these items as soon as possible; they have the highest technical severity in this scan.", "pt-BR": "Trate estes itens o quanto antes; eles têm a maior gravidade técnica desta varredura.", "ru": "Устраните эти проблемы как можно скорее: у них наивысшая техническая серьёзность в этом сканировании."},
    "high": {"en": "Important technical issues were identified. Plan corrective work with priority.", "pt-BR": "Foram identificados problemas técnicos importantes. Planeje a correção com prioridade.", "ru": "Обнаружены важные технические проблемы. Запланируйте их устранение в приоритетном порядке."},
    "medium": {"en": "Review the listed improvements and address them as part of routine maintenance.", "pt-BR": "Revise as melhorias listadas e trate-as durante a manutenção de rotina.", "ru": "Проверьте перечисленные улучшения и устраните их в ходе планового обслуживания."},
    "low": {"en": "Few high-severity signals were identified. Review the listed items when practical.", "pt-BR": "Foram identificados poucos sinais de gravidade alta. Revise os itens quando possível.", "ru": "Обнаружено мало признаков высокой серьёзности. Проверьте перечисленные пункты, когда будет возможность."},
    "none": {"en": "No finding records were returned, but this does not prove that the network has no security issues.", "pt-BR": "A varredura não retornou registros de achados, mas isso não comprova que a rede não tenha problemas de segurança.", "ru": "Записи о находках не получены, но это не доказывает отсутствие проблем безопасности в сети."},
}

_PURPLE = colors.HexColor("#600BB5")
_INK = colors.HexColor("#1F2937")
_MUTED = colors.HexColor("#52606D")
_LIGHT = colors.HexColor("#F5F2F8")
_LINE = colors.HexColor("#DDD6E7")


class HorizontalBarChart(Flowable):
    """Small vector chart with direct labels and values; no inferred score scale."""

    def __init__(self, rows: list[tuple[str, int]], *, width: float, font_name: str):
        super().__init__()
        self.rows = rows
        self.width = width
        self.font_name = font_name
        self.row_height = 30 if any("\n" in label for label, _ in rows) else 19
        self.height = max(24, len(rows) * self.row_height + 4)

    def draw(self) -> None:
        canvas = self.canv
        label_width = min(74 * mm, self.width * 0.38)
        count_width = 12 * mm
        track_x = label_width
        track_width = self.width - label_width - count_width - 3 * mm
        max_value = max((value for _, value in self.rows), default=0)
        for index, (label, value) in enumerate(self.rows):
            y = self.height - (index + 1) * self.row_height + 5
            canvas.setFont(self.font_name, 8.5)
            canvas.setFillColor(_INK)
            for line_index, label_line in enumerate(label.split("\n")[:2]):
                canvas.drawString(0, y + 3 - line_index * 10, _fit_chart_label(_clean_text(label_line), label_width, self.font_name, 8.5))
            canvas.setFillColor(_LIGHT)
            canvas.roundRect(track_x, y, track_width, 11, 4, stroke=0, fill=1)
            if max_value:
                bar_width = track_width * value / max_value
                if bar_width > 0:
                    canvas.setFillColor(_PURPLE)
                    canvas.roundRect(track_x, y, max(3, bar_width), 11, 4, stroke=0, fill=1)
            canvas.setFillColor(_INK)
            canvas.drawRightString(self.width, y + 2, str(value))


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
    buffer = BytesIO()
    document = ScanReportDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=24 * mm,
        bottomMargin=20 * mm,
        title=f"Dmitri - {report.kind} scan report",
        author="Dmitri",
    )
    styles = getSampleStyleSheet()
    font_name, bold_font_name = _register_unicode_fonts()
    styles.add(ParagraphStyle("ReportTitle", parent=styles["Title"], fontName=bold_font_name, fontSize=21, leading=25, textColor=_PURPLE, alignment=TA_LEFT, spaceAfter=2))
    styles.add(ParagraphStyle("ReportSubTitle", parent=styles["Heading2"], fontName=bold_font_name, fontSize=11, leading=15, textColor=_MUTED, spaceAfter=4))
    styles.add(ParagraphStyle("ReportHeading", parent=styles["Heading2"], fontName=bold_font_name, fontSize=12, leading=16, textColor=_PURPLE, spaceBefore=11, spaceAfter=5, keepWithNext=True))
    styles.add(ParagraphStyle("ReportChapter", parent=styles["ReportHeading"], fontSize=13, leading=18))
    styles.add(ParagraphStyle("ReportDevice", parent=styles["ReportHeading"]))
    styles.add(ParagraphStyle("ReportBody", parent=styles["BodyText"], fontName=font_name, fontSize=9, leading=13, textColor=_INK, spaceAfter=3))
    styles.add(ParagraphStyle("ReportSmall", parent=styles["BodyText"], fontName=font_name, fontSize=7.5, leading=10, textColor=_MUTED))
    styles.add(ParagraphStyle("ReportCard", parent=styles["BodyText"], fontName=font_name, fontSize=8.5, leading=12, textColor=_INK))
    styles["Code"].fontName = font_name
    copy = _COPY[report.language]
    document.contents_label = copy["contents"]
    if report.kind == "explained":
        metrics = report.sections.get("metrics") or {}
        device_labels = {
            device["address"]: device.get("display_name", device["machine_type"])
            for device in (report.sections.get("education") or {}).get("devices", [])
        }
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
            (copy["hosts"], metrics.get("hosts_scanned", 0)),
            (copy["findings"], metrics.get("finding_records", 0)),
            (copy["cves"], metrics.get("unique_cve_ids", 0)),
            (copy["ports"], metrics.get("open_ports", 0)),
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
             Paragraph(escape(_format_timestamp(report.sections.get("scan_timestamp"))), styles["ReportCard"])],
            [Paragraph(f"<b>{escape(copy['scope'])}</b>", styles["ReportCard"]),
             Paragraph(escape(_clean_text(report.sections.get("scope") or "-")), styles["ReportCard"])],
            [Paragraph(f"<b>{escape(copy['mode'])}</b>", styles["ReportCard"]),
             Paragraph(escape(_scan_mode_label(report.sections.get("scan_mode"), report.language)), styles["ReportCard"])],
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
        story: list[Any] = [
            hero,
            Spacer(1, 9 * mm),
            Paragraph(copy["intro"], styles["ReportBody"]),
            Spacer(1, 5 * mm),
            Paragraph(copy["overview"], styles["ReportHeading"]),
            Paragraph(escape(_clean_text(report.sections.get("overview") or copy["none"])), styles["ReportBody"]),
            Spacer(1, 7 * mm),
            metric_table,
            Paragraph(copy["hosts_chart"], styles["ReportHeading"]),
            HorizontalBarChart(
                [
                    (
                        device_labels.get(str(host.get("address")), str(host.get("hostname") or host.get("address") or "-")) + "\n" + str(host.get("address") or "-"),
                        int(host.get("findings", 0)),
                    )
                    for host in (report.sections.get("top_hosts") or [])[:3]
                ],
                width=document.width - 12,
                font_name=font_name,
            ),
            Spacer(1, 8 * mm),
            metadata,
            Spacer(1, 5 * mm),
            Paragraph(f"ID: {escape(str(report.scan_id))}", styles["ReportSmall"]),
        ]
    else:
        story = [
            Paragraph("Dmitri", styles["ReportTitle"]),
            Paragraph(copy[report.kind], styles["ReportSubTitle"]),
            Paragraph(f"{copy['generated']}: {escape(_clean_text(report.generated_at.strftime('%d/%m/%Y %H:%M UTC')))} | ID: {escape(str(report.scan_id))}", styles["ReportSmall"]),
            Paragraph(
                f"{copy['scan_timestamp']}: {escape(_format_timestamp(report.sections.get('scan_timestamp')))} | "
                f"{copy['scope']}: {escape(_clean_text(report.sections.get('scope') or '-'))}",
                styles["ReportSmall"],
            ),
            Paragraph(
                f"{copy['mode']}: {escape(_scan_mode_label(report.sections.get('scan_mode'), report.language))}",
                styles["ReportSmall"],
            ),
            Spacer(1, 7 * mm),
        ]
    if report.kind == "explained":
        toc_styles = [
            ParagraphStyle(
                "TOCChapter",
                fontName=bold_font_name,
                fontSize=10,
                leading=14,
                textColor=_PURPLE,
                leftIndent=0,
                firstLineIndent=0,
                spaceBefore=3,
            ),
            ParagraphStyle(
                "TOCDetail",
                fontName=font_name,
                fontSize=7.2,
                leading=8.4,
                textColor=_INK,
                leftIndent=5,
                firstLineIndent=0,
                spaceBefore=0,
            ),
        ]
        contents = CompactTableOfContents(toc_styles, bold_font_name, font_name)
        story.extend([
            PageBreak(),
            Paragraph(copy["contents"], styles["ReportChapter"]),
            contents,
            PageBreak(),
        ])
        _append_explained(story, report.sections, styles, copy, report.language, document.width, font_name)
    else:
        _append_technical(story, report.sections, styles, copy)
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


def _append_explained(story: list[Any], sections: dict[str, Any], styles: Any, copy: dict[str, str], language: AILanguage, width: float, font_name: str) -> None:
    story.extend([Paragraph(copy["intro"], styles["ReportBody"]), Spacer(1, 3 * mm)])
    level = str(sections.get("attention_level", "unknown"))
    level_label = (
        copy["level_none"] if level == "none" else copy.get(level, copy["default"])
    )
    summary = Table([[Paragraph(f"<b>{escape(copy['attention'])}: {escape(level_label)}</b>", styles["ReportCard"])], [Paragraph(escape(_clean_text(sections.get("overview") or copy["none"])), styles["ReportCard"]) ]], colWidths=[width])
    summary.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), _LIGHT), ("BOX", (0, 0), (-1, -1), 0.7, _LINE), ("LINEBELOW", (0, 0), (-1, 0), 0.4, _LINE), ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    story.extend([summary, Paragraph(copy["interpret"], styles["ReportHeading"]), Paragraph(escape(_clean_text(_LEVELS.get(level, {}).get(language, copy["default"]))), styles["ReportBody"])])

    metrics = sections.get("metrics") or {}
    kpis = [
        (copy["hosts"], metrics.get("hosts_scanned", 0)),
        (copy["findings"], metrics.get("finding_records", 0)),
        (copy["cves"], metrics.get("unique_cve_ids", 0)),
        (copy["ports"], metrics.get("open_ports", 0)),
    ]
    cards = [[Paragraph(f"<b>{value}</b><br/>{escape(label)}", styles["ReportCard"]) for label, value in kpis]]
    kpi_table = Table(cards, colWidths=[width / 4] * 4)
    kpi_table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.white), ("BOX", (0, 0), (-1, -1), 0.6, _LINE), ("INNERGRID", (0, 0), (-1, -1), 0.4, _LINE), ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story.extend([Spacer(1, 3 * mm), kpi_table])
    if sections.get("education"):
        append_education(story, sections, styles, copy, language, width, font_name)
        return
    story.append(Paragraph(copy["severity_chart"], styles["ReportHeading"]))
    severity_counts = sections.get("severity_counts") or {}
    severity_rows = [(_SEVERITY[key][language], int(severity_counts.get(key, 0))) for key in ("critical", "high", "medium", "low")]
    story.extend([HorizontalBarChart(severity_rows, width=width, font_name=font_name), Paragraph(copy["severity_note"], styles["ReportSmall"])])

    story.append(Paragraph(copy["hosts_chart"], styles["ReportHeading"]))
    hosts = sections.get("top_hosts") or []
    if hosts:
        host_rows = [(str(host.get("hostname") or host.get("address") or "-"), int(host.get("findings", 0))) for host in hosts[:5]]
        story.append(HorizontalBarChart(host_rows, width=width, font_name=font_name))
    else:
        story.append(Paragraph(copy["no_hosts"], styles["ReportBody"]))

    story.append(Paragraph(copy["first"], styles["ReportHeading"]))
    actions = sections.get("what_to_do_first") or []
    if actions:
        for index, action in enumerate(actions, start=1):
            if isinstance(action, dict):
                title = action.get("title") or action.get("action") or ""
                detail = action.get("description") or action.get("explanation") or ""
                priority = action.get("priority")
                prefix = f"{index}. "
                if priority:
                    prefix += f"[{_priority_label(str(priority), language)}] "
                body = f"<b>{escape(_clean_text(prefix + str(title)))}</b>"
                if detail:
                    body += f"<br/>{escape(_clean_text(detail))}"
            else:
                body = f"{index}. {escape(_clean_text(action))}"
            story.append(Paragraph(body, styles["ReportBody"]))
    else:
        story.append(Paragraph(copy["no_findings"], styles["ReportBody"]))

    findings = sections.get("important_findings") or []
    details_heading = Paragraph(copy["details"], styles["ReportHeading"])
    if not findings:
        story.append(details_heading)
        story.append(Paragraph(copy["no_findings"], styles["ReportBody"]))
    for index, finding in enumerate(findings[:5], start=1):
        card = _finding_card(index, finding, styles, copy, language, width)
        if index == 1:
            # Avoid leaving the section heading alone at the foot of a page.
            story.append(KeepTogether([details_heading, *card[:1]]))
            story.extend(card[1:])
        else:
            story.extend(card)
        story.append(Spacer(1, 3 * mm))

    story.append(Paragraph(copy["method"], styles["ReportHeading"]))
    story.append(Paragraph(escape(_clean_text(sections.get("method") or "")), styles["ReportBody"]))
    story.append(Paragraph(copy["limitations"], styles["ReportHeading"]))
    for limitation in sections.get("limitations") or []:
        story.append(Paragraph(f"- {escape(_clean_text(limitation))}", styles["ReportBody"]))
    story.extend([Paragraph(copy["next"], styles["ReportHeading"]), Paragraph(copy["next_body"], styles["ReportBody"])])


def _finding_card(index: int, finding: dict[str, Any], styles: Any, copy: dict[str, str], language: AILanguage, width: float) -> list[Any]:
    severity = str(finding.get("severity", ""))
    host = finding.get("hostname") or copy["default"]
    address = finding.get("address")
    heading = f"<b>{index}. {escape(_clean_text(finding.get('title') or copy['default']))}</b>"
    metadata = [f"{copy['severity']}: {_SEVERITY.get(severity, {}).get(language, copy['default'])}"]
    if host:
        metadata.append(str(host))
    if address:
        metadata.append(f"{copy['address']}: {address}")
    if finding.get("service"):
        service = str(finding["service"])
        if finding.get("port"):
            service += f" ({finding['port']})"
        metadata.append(f"{copy['service']}: {service}")
    if finding.get("cvss_score") is not None:
        metadata.append(f"{copy['cvss']}: {finding['cvss_score']}")
    description = finding.get("plain_language_explanation") or finding.get("description")
    paragraphs: list[Any] = []
    if description:
        description_text = _clean_text(description)
        lead, continuation = _split_description(description_text)
        lead_paragraph = Paragraph(
            f"<b>{copy['description']}:</b> {escape(lead)}",
            styles["ReportCard"],
        )
        # Keep a bounded introduction with the finding identity. The remaining
        # text stays in its own splittable paragraph so long evidence cannot
        # force an over-height table row or a LayoutError.
        paragraphs.append(
            KeepTogether(
                [
                    Paragraph(heading, styles["ReportCard"]),
                    Paragraph(
                        escape(_clean_text(" / ".join(metadata))),
                        styles["ReportSmall"],
                    ),
                    Spacer(1, 2 * mm),
                    lead_paragraph,
                ]
            )
        )
        if continuation:
            paragraphs.append(Paragraph(escape(continuation), styles["ReportCard"]))
    else:
        paragraphs.extend(
            [
                Paragraph(heading, styles["ReportCard"]),
                Paragraph(
                    escape(_clean_text(" / ".join(metadata))),
                    styles["ReportSmall"],
                ),
            ]
        )
    if finding.get("why_it_matters"):
        paragraphs.append(Paragraph(f"<b>{copy['why']}:</b> {escape(_clean_text(finding['why_it_matters']))}", styles["ReportCard"]))
    if finding.get("recommendation"):
        paragraphs.append(Paragraph(f"<b>{copy['recommendation']}:</b> {escape(_clean_text(finding['recommendation']))}", styles["ReportCard"]))
    if finding.get("evidence"):
        paragraphs.append(Paragraph(f"<b>{copy['evidence']}:</b> {escape(_clean_text(finding['evidence']))}", styles["ReportSmall"]))
    if finding.get("uncertainty"):
        paragraphs.append(Paragraph(f"<b>{copy['uncertainty']}:</b> {escape(_clean_text(finding['uncertainty']))}", styles["ReportSmall"]))
    # Paragraphs can flow across pages; keeping a whole finding in one table cell
    # can produce a LayoutError when scanner evidence is unusually long.
    return paragraphs


def _split_description(value: str, limit: int = 260) -> tuple[str, str]:
    if len(value) <= limit:
        return value, ""
    split_at = value.rfind(" ", 0, limit + 1)
    if split_at <= 0:
        split_at = limit
    return f"{value[:split_at].rstrip()}...", value[split_at:].lstrip()


def _fit_chart_label(label: str, width: float, font_name: str, font_size: float) -> str:
    label = " ".join(label.split())
    if pdfmetrics.stringWidth(label, font_name, font_size) <= width:
        return label
    suffix = "..."
    while label and pdfmetrics.stringWidth(label + suffix, font_name, font_size) > width:
        label = label[:-1]
    return label + suffix


def _priority_label(priority: str, language: AILanguage) -> str:
    labels = {
        "immediate": {"en": "Immediate", "pt-BR": "Imediata", "ru": "Срочно"},
        "high": {"en": "High", "pt-BR": "Alta", "ru": "Высокий"},
        "medium": {"en": "Medium", "pt-BR": "Moderada", "ru": "Средний"},
        "low": {"en": "Low", "pt-BR": "Baixa", "ru": "Низкий"},
    }
    return labels.get(priority, {}).get(language, priority)


def _scan_mode_label(mode: object, language: AILanguage) -> str:
    normalized = _clean_text(mode).casefold()
    return _SCAN_MODES[language].get(normalized, normalized or "-")


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


def _append_technical(story: list[Any], sections: dict[str, Any], styles: Any, copy: dict[str, str]) -> None:
    story.extend([Paragraph(copy["technical_data"], styles["ReportHeading"]), Preformatted(_pretty_json(sections.get("scan")), styles["Code"], maxLineLength=100), PageBreak(), Paragraph(copy["risk"], styles["ReportHeading"]), Preformatted(_pretty_json(sections.get("risk_summary")), styles["Code"], maxLineLength=100), Spacer(1, 10), Paragraph(copy["ai"], styles["ReportHeading"]), Preformatted(_pretty_json(sections.get("ai_analysis")), styles["Code"], maxLineLength=100)])


def _clean_text(value: object) -> str:
    text = str(value or "")
    text = text.replace("\u2010", "-").replace("\u2011", "-").replace("\u2012", "-").replace("\u2013", "-").replace("\u2014", "-").replace("\u2212", "-").replace("\u2022", "-")
    text = text.replace("\u2018", "'").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    return unicodedata.normalize("NFC", text)


def _pretty_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, indent=2, default=str)
