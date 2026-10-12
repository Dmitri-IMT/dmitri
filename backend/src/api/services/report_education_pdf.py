"""Teaching pages and vector graphics for the explained scan report."""

from __future__ import annotations

from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    CondPageBreak,
    Flowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from api.services.report_education_copy import guide, text

_INK = colors.HexColor("#1F2937")
_LIGHT = colors.HexColor("#F5F2F8")
_PURPLE = colors.HexColor("#600BB5")
_SEVERITY_COLORS = ("#B42336", "#CC6430", "#AB8519", "#487394")
_SEVERITIES = ("critical", "high", "medium", "low")
_LABELS = {
    "en": ("Critical", "High", "Medium", "Low", "Service / version", "Records"),
    "pt-BR": ("Crítica", "Alta", "Moderada", "Baixa", "Serviço / versão", "Registros"),
    "ru": ("Критическая", "Высокая", "Средняя", "Низкая", "Служба / версия", "Записи"),
}
_ACTION_PRIORITY = {
    "en": {
        "immediate": "Immediate",
        "high": "High",
        "medium": "Medium",
        "low": "Low",
    },
    "pt-BR": {
        "immediate": "Imediata",
        "high": "Alta",
        "medium": "Moderada",
        "low": "Baixa",
    },
    "ru": {
        "immediate": "Срочно",
        "high": "Высокий",
        "medium": "Средний",
        "low": "Низкий",
    },
}


def _safe(value: Any) -> str:
    return escape(str(value if value is not None else "-"))


class EvidenceBars(Flowable):
    """Stacked counts with a common scale, including zero-count devices."""

    def __init__(self, rows, legends, palette, width, font_name, *, maximum=None):
        super().__init__()
        self.rows = rows
        self.legends = legends
        self.palette = [colors.HexColor(value) for value in palette]
        self.color_codes = palette
        self.width = width
        self.font_name = font_name
        self.legend_gap = 20 if any("\n" in str(label) for label, _ in rows) else 8
        self.height = len(rows) * 24 + len(legends) * 14 + self.legend_gap
        self.maximum = (max((sum(values) for _, values in rows), default=0)
                        if maximum is None else maximum)

    def split(self, availWidth, availHeight):
        row_count = int((availHeight - len(self.legends) * 14 - self.legend_gap) // 24)
        if row_count < 1 or row_count >= len(self.rows):
            return []
        return [EvidenceBars(
            rows, self.legends, self.color_codes, self.width, self.font_name,
            maximum=self.maximum,
        ) for rows in (self.rows[:row_count], self.rows[row_count:])]

    def draw(self):
        canvas = self.canv
        canvas.setFont(self.font_name, 8)
        label_width = self.width * .37
        track_width = self.width - label_width - 32
        maximum = self.maximum
        for index, (label, values) in enumerate(self.rows):
            y = self.height - 20 - index * 24
            canvas.setFillColor(_INK)
            # Rows use short, factual labels: IP addresses or service groups.
            for line_index, label_line in enumerate(str(label).split("\n")[:2]):
                while (canvas.stringWidth(label_line, self.font_name, 8)
                       > label_width - 5):
                    label_line = label_line[:-4] + "..."
                canvas.drawString(0, y + 2 - line_index * 10, label_line)
            canvas.setFillColor(_LIGHT)
            canvas.rect(label_width, y, track_width, 11, stroke=0, fill=1)
            x = label_width
            for count, color in zip(values, self.palette, strict=True):
                length = track_width * count / maximum if maximum else 0
                if length:
                    canvas.setFillColor(color)
                    canvas.rect(x, y, length, 11, stroke=0, fill=1)
                x += length
            canvas.setFillColor(_INK)
            canvas.drawRightString(self.width, y + 2, str(sum(values)))
        for index, (label, color) in enumerate(
            zip(self.legends, self.palette, strict=True)
        ):
            y = len(self.legends) * 14 - index * 14
            canvas.setFillColor(color)
            canvas.rect(0, y, 8, 8, stroke=0, fill=1)
            canvas.setFillColor(_INK)
            canvas.drawString(13, y, label)


class AttackPath(Flowable):
    """A conditional incident sequence, not a claim that an attack occurred."""

    def __init__(self, labels, width, style):
        super().__init__()
        self.width = width
        self.height = 76
        self.labels = labels
        self.style = style

    def draw(self):
        size = (self.width - 36) / 4
        for index, label in enumerate(self.labels):
            x = index * (size + 12)
            self.canv.setStrokeColor(_PURPLE)
            self.canv.setFillColor(_LIGHT)
            self.canv.roundRect(x, 5, size, 64, 5, stroke=1, fill=1)
            paragraph = Paragraph(f"<b>{index + 1}</b><br/>{_safe(label)}", self.style)
            _, height = paragraph.wrap(size - 14, 60)
            paragraph.drawOn(self.canv, x + 7, 37 - height / 2)
            if index < 3:
                self.canv.line(x + size + 2, 37, x + size + 10, 37)
                self.canv.line(x + size + 7, 40, x + size + 10, 37)
                self.canv.line(x + size + 7, 34, x + size + 10, 37)


def _table(rows, widths):
    table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _LIGHT),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#FAFAFC")]),
        ("LINEBELOW", (0, 0), (-1, 0), .7, _PURPLE),
        ("LINEBELOW", (0, 1), (-1, -1), .25, colors.HexColor("#DDD6E7")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return table


def append_education(story, sections, styles, copy, language, width, font_name):
    education = sections["education"]
    devices = education["devices"]
    labels = _LABELS[language]
    chart_width = width - 12

    def p(value, style="ReportBody"):
        return Paragraph(_safe(value), styles[style])

    def body(value):
        story.append(p(value))

    def lesson(key, **values):
        body(text(key, language, **values))

    def heading(key, *, new_page=False):
        if new_page:
            story.append(PageBreak())
        style = "ReportChapter" if key.endswith("title") or key == "dashboard" \
            else "ReportHeading"
        story.append(p(text(key, language), style))

    def field(label, value, style="ReportBody"):
        if value:
            story.append(Paragraph(
                f"<b>{_safe(label)}:</b> {_safe(value)}", styles[style]
            ))

    if any(device["finding_count"] for device in devices):
        first = max(devices, key=lambda device: device["finding_count"])
        lesson("start_here", address=first["address"], count=first["finding_count"],
               groups=", ".join(first["groups"]))
    for group in education["issue_groups"]:
        if group["family"] == "shell":
            lesson("shell_priority", address=group["address"], port=group["port"],
                   group=group["id"])
    heading("reading_title")
    for key in ("reading_intro", "finding_lesson", "ports_lesson"):
        lesson(key)
    heading("dashboard", new_page=True)
    lesson("counts_note", affected=education["affected_hosts"], hosts=len(devices),
           without=education["hosts_without_findings"])
    counts = sections["severity_counts"]
    story.append(p(copy["severity_chart"], "ReportHeading"))
    story.append(EvidenceBars(
        [(labels[index], [counts[key] if column == index else 0
                          for column in range(4)])
         for index, key in enumerate(_SEVERITIES)],
        labels[:4], _SEVERITY_COLORS, chart_width, font_name,
    ))
    lesson("severity_lesson")
    story.append(p(copy["hosts_chart"], "ReportHeading"))
    story.append(EvidenceBars(
        [(device.get("display_name", device["machine_type"]) + "\n"
          + device["address"],
          [device["severity_counts"][key] for key in _SEVERITIES])
         for device in devices],
        labels[:4], _SEVERITY_COLORS, chart_width, font_name,
    ))
    total = sum(device["finding_count"] for device in devices)
    if total:
        largest = max(devices, key=lambda item: item["finding_count"])
        lesson("concentration", address=largest["address"],
               count=largest["finding_count"], total=total,
               share=round(largest["finding_count"] / total * 100, 1))
    heading("severity_scale", new_page=True)
    for key in _SEVERITIES:
        lesson("severity_" + key)

    heading("evidence_title")
    evidence = education["evidence_counts"]
    keys = ("correlation", "observation", "other")
    story.append(EvidenceBars(
        [(text("basis_" + key, language), [evidence[key] if column == index else 0
                                          for column in range(3)])
         for index, key in enumerate(keys)],
        [text("basis_" + key, language) for key in keys],
        ("#600BB5", "#287B8E", "#74808B"), chart_width, font_name,
    ))
    for key in ("evidence_lesson", "correlation_limit", "reachability"):
        lesson(key)
    completeness = education["evidence_completeness"]
    lesson("coverage_" + completeness)
    if education["coverage_recorded"]:
        lesson("coverage_numbers", completed=education["checks_completed"],
               incomplete=education["checks_incomplete"])
    else:
        lesson("coverage_missing")
    if any(education["enrichment"].values()):
        lesson("enrichment_pending", **education["enrichment"])
    if education["unassigned_findings"]:
        lesson("unassigned", count=education["unassigned_findings"])
    heading("service_counts")
    families = education["service_counts"]
    if families:
        story.append(EvidenceBars(
            [(guide(key, language)["name"], [value])
             for key, value in sorted(families.items(), key=lambda item: -item[1])],
            [copy["ports"]], ("#287B8E",), chart_width, font_name,
        ))
    lesson("service_counts_note")

    heading("device_title", new_page=True)
    lesson("identity_note")
    lesson("identity_confidence_note")
    for index, device in enumerate(devices):
        if index:
            story.append(Spacer(1, 5 * mm))
        device_start = len(story)
        story.append(p(
            f"{device.get('display_name', device['machine_type'])} | "
            f"{device['address']}", "ReportDevice"
        ))
        field(text("device_status_" + device["status"], language),
              f"{device['finding_count']} {labels[5]} / "
              f"{device['open_ports']} {copy['ports']}")
        body(device["machine_type"] + (" | " + device["os"] if device["os"] else ""))
        confidence = device.get("identity_confidence", "unknown")
        field(text("identity_confidence", language),
              text("identity_" + confidence, language))
        field(text("identity_manufacturer", language), device.get("manufacturer"))
        field(text("identity_model", language), device.get("model"))
        if device.get("identity_evidence"):
            field(text("identity_basis", language),
                  "; ".join(device["identity_evidence"][:3]))
        if device.get("identity_conflicts"):
            field(text("identity_conflict", language),
                  "; ".join(device["identity_conflicts"]))
        body(device["note"])
        if device["review_exposures"]:
            lesson("device_exposure_review", count=device["review_exposures"])
        if device["groups"]:
            field(copy["details"], ", ".join(device["groups"]))
        if device["unreadable_fields"]:
            field(copy["uncertainty"], ", ".join(device["unreadable_fields"]))
        if device["services"]:
            story.append(CondPageBreak(45 * mm))
        story.append(p(text("services", language), "ReportHeading"))
        # Keep the heading with a bounded spacer, so a long inventory table can
        # start here and split normally instead of moving to the next page.
        story.append(Spacer(1, 1))
        if not device["services"]:
            lesson("no_ports")
            # A short zero-port card reads as a single unit; avoid moving its
            # final explanation away from the device identity.
            card = story[device_start:]
            del story[device_start:]
            story.append(KeepTogether(card))
            continue
        rows = [[p(copy["ports"] + " | " + device["address"], "ReportSmall"),
                 p(labels[4], "ReportSmall"),
                 p(text("purpose", language), "ReportSmall")]]
        for service in device["services"]:
            rows.append([
                p(f"{service['port']}/{service['protocol']}", "ReportSmall"),
                p(f"{service['service']}\n{service['version'] or '-'}", "ReportSmall"),
                p(service["purpose"], "ReportSmall"),
            ])
        story.append(_table(rows, [width * .14, width * .29, width * .57]))

    heading("group_title", new_page=True)
    lesson("group_intro")
    for index, group in enumerate(education["issue_groups"]):
        if index:
            story.append(PageBreak())
        story.append(p(
            f"{group['id']} | {group['title']} | {group['address'] or '-'}",
            "ReportHeading",
        ))
        endpoint = f"{group['port']}/{group['protocol']}" if group["port"] else "-"
        metadata = (f"{copy['ports']}: {endpoint} | {labels[5]}: "
                    f"{group['finding_count']} | "
                    + text("basis_" + group["basis"], language))
        body(metadata)
        if group["basis"] in {"correlation", "service"}:
            lesson("group_" + group["basis"], count=group["finding_count"],
                   version=group["version"] or text("version_unknown", language))
        for key in ("purpose", "meaning", "impact"):
            field(text(key, language), group[key])
        field(copy["uncertainty"], group["uncertainty"])
        body(group["conditions"])
        for note in group["advisory_notes"]:
            field(note["cve_id"], note["explanation"])
            story.append(Paragraph(
                f'<link href="{_safe(note["url"])}" color="#600BB5">'
                f'{_safe(note["url"])}</link>', styles["ReportSmall"]
            ))
        for observation in group["recorded_observations"]:
            field(copy["description"], observation["description"])
            field(copy["evidence"], observation["evidence"], "ReportSmall")
        story.append(p(text("step", language), "ReportHeading"))
        for number, step in enumerate(group["steps"], start=1):
            body(f"{number}. {step}")
        field(text("verify", language), group["verify"])

    heading("path_title", new_page=True)
    lesson("path_intro")
    path = ("access", "service", "flaw", "impact")
    story.append(AttackPath(
        [text("path_" + key, language) for key in path],
        chart_width, styles["ReportCard"]
    ))
    for key in path:
        field(text("path_" + key, language), text("path_" + key + "_detail", language))
    heading("safety_title")
    lesson("safety_body")
    for device in devices:
        if not device["finding_count"]:
            body(f"{device['address']}: {device['open_ports']} {copy['ports']}; "
                 + text("device_status_no_alerts", language) + ".")

    heading("plan_title", new_page=True)
    field(text("plan_owner", language), text("plan_owner_body", language))
    actions = sections.get("what_to_do_first") or []
    if actions:
        story.append(p(copy["first"], "ReportHeading"))
        for action in actions:
            if isinstance(action, dict):
                title = str(action.get("title") or "")
                priority = _ACTION_PRIORITY.get(language, {}).get(
                    str(action.get("priority") or "")
                )
                if priority:
                    title = f"{priority}: {title}" if title else priority
                field(title, action.get("description", ""))
            else:
                body(action)
    for number in range(1, 7):
        story.append(KeepTogether([
            p(f"{number}. " + text(f"plan_{number}_title", language), "ReportHeading"),
            p(text(f"plan_{number}_body", language)),
        ]))
    # Retain individually generated explanations and recommendations when AI is
    # available; this supplement also preserves the original top finding text.
    important = [finding for finding in sections.get("important_findings", [])
                 if finding.get("plain_language_explanation")
                 or finding.get("why_it_matters")]
    if important:
        story.append(PageBreak())
        story.append(p(copy["details"], "ReportHeading"))
        for finding in important:
            story.append(p(
                f"{finding['address'] or '-'} | {finding['title']}", "ReportHeading"
            ))
            field(copy["description"], finding.get("plain_language_explanation")
                  or finding.get("description"))
            for key, label in (("why_it_matters", "why"),
                               ("recommendation", "recommendation"),
                               ("evidence", "evidence"),
                               ("uncertainty", "uncertainty")):
                field(copy[label], finding.get(key))

    heading("glossary_title", new_page=True)
    for key in ("ip", "patch", "cvss", "cve", "exploit", "segmentation",
                "service", "authentication", "permissions", "encryption",
                "key", "firewall", "client", "firmware", "banner", "backup"):
        lesson("glossary_" + key)
    heading("register_title", new_page=True)
    lesson("register_note")
    rows = [[p(copy["address"], "ReportSmall"), p("CVE / Gxx", "ReportSmall"),
             p(copy["severity"], "ReportSmall"),
             p(text("register_effects", language), "ReportSmall")]]
    group_names = {group["id"]: group["title"]
                   for group in education["issue_groups"]}
    for record in education["appendix"]:
        effect = " / ".join(record["advisory_effects"])
        if not effect:
            effect = text("advisory_unclassified" if record["advisory_description"]
                          else "advisory_missing", language)
        if record["basis"] == "observation":
            effect = text("basis_observation", language)
        title = record["title"] if record["reference"] else group_names[record["group"]]
        identity = f"{record['group']} | {title}"
        if record["reference"]:
            identity_cell = Paragraph(
                f'<link href="{_safe(record["reference"])}" color="#600BB5">'
                f'{_safe(identity)}</link>', styles["ReportSmall"]
            )
        else:
            identity_cell = p(identity, "ReportSmall")
        rows.append([
            p(f"{record['address'] or '-'} | {record['port'] or '-'}", "ReportSmall"),
            identity_cell,
            p(labels[_SEVERITIES.index(record["severity"])], "ReportSmall"),
            p(effect, "ReportSmall"),
        ])
    if len(rows) > 1:
        story.append(_table(rows, [width * .21, width * .25, width * .13, width * .41]))
    else:
        body(copy["no_findings"])
    heading("sources_title", new_page=True)
    lesson("sources_note")
    for source in education["sources"]:
        body(source["title"])
        story.append(Paragraph(
            f'<link href="{_safe(source["url"])}" color="#600BB5">'
            f'{_safe(source["url"])}</link>', styles["ReportSmall"]
        ))
        story.append(Spacer(1, 3 * mm))
    story.append(p(copy["method"], "ReportHeading"))
    body(sections["method"])
    story.append(p(copy["limitations"], "ReportHeading"))
    for limitation in sections["limitations"]:
        body(limitation)
