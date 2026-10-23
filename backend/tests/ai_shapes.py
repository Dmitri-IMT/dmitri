from __future__ import annotations

from uuid import UUID, uuid4

from api.schemas.ai import (
    AIFindingNote,
    AIFixTask,
    AIProviderFindingNote,
    AIProviderFixTask,
    ProviderScanAIAnalysis,
    ProviderScanAIChildAnalysis,
    ScanAIAnalysis,
)


def provider_task(
    *refs: str,
    title: str = "Update the software on machine_1",
    time: str = "30_minutes",
    steps: tuple[str, ...] = ("Install the latest update from the vendor.",),
) -> AIProviderFixTask:
    return AIProviderFixTask(
        title=title,
        who="it_person",
        time=time,
        steps=list(steps),
        fallback=None,
        fixes_fully=True,
        fixes=list(refs or ("finding_1",)),
    )


def provider_note(ref: str = "finding_1") -> AIProviderFindingNote:
    return AIProviderFindingNote(
        finding_ref=ref,
        plain_title="Someone on your network can reach this service",
        cause="The machine runs old software with a known flaw.",
        what_could_happen="Someone could take control of the machine.",
    )


def provider_analysis(
    *,
    summary: str = "One machine needs an update this week.",
    tasks: list[AIProviderFixTask] | None = None,
    findings: list[AIProviderFindingNote] | None = None,
    not_checked: str | None = None,
) -> ProviderScanAIAnalysis:
    return ProviderScanAIAnalysis(
        summary=summary,
        tasks=[provider_task()] if tasks is None else tasks,
        findings=[provider_note()] if findings is None else findings,
        not_checked=not_checked,
    )


def empty_analysis() -> ProviderScanAIAnalysis:
    return provider_analysis(
        summary="Nothing urgent came up in this scan.", tasks=[], findings=[]
    )


def child_analysis(
    tasks: list[AIProviderFixTask] | None = None,
    findings: list[AIProviderFindingNote] | None = None,
) -> ProviderScanAIChildAnalysis:
    return ProviderScanAIChildAnalysis(tasks=tasks or [], findings=findings or [])


def stored_analysis(finding_id: UUID | None = None) -> ScanAIAnalysis:
    finding_id = finding_id or uuid4()
    return ScanAIAnalysis(
        summary="One machine needs an update this week.",
        tasks=[
            AIFixTask(
                rank=1,
                priority="high",
                title="Update the software on edge-router",
                who="it_person",
                time="30_minutes",
                steps=["Install the latest update from the vendor."],
                fallback=None,
                fixes_fully=True,
                finding_ids=[finding_id],
                highest_risk_score=80,
                sources=[],
            )
        ],
        findings=[
            AIFindingNote(
                finding_id=finding_id,
                plain_title="Someone on your network can reach this service",
                cause="The machine runs old software with a known flaw.",
                what_could_happen="Someone could take control of the machine.",
                task_rank=1,
            )
        ],
        not_checked=None,
    )
