from types import SimpleNamespace

from api.services.ai.chat import _select_findings


def _finding(title: str, service: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        title=title,
        description="description",
        recommendation="recommendation",
        service=service,
        cve_id=None,
        host_ip=None,
        host_hostname=None,
    )


def test_question_relevance_moves_matching_finding_to_front() -> None:
    findings = [_finding("Atualizar OpenSSH"), _finding("Senha fraca", "modbus")]

    selected = _select_findings(findings, "o que devo corrigir no modbus?")

    assert selected[0].service == "modbus"
    assert selected[1].title == "Atualizar OpenSSH"


def test_question_selection_remains_bounded_and_stable_without_terms() -> None:
    findings = [_finding("Primeiro"), _finding("Segundo")]

    selected = _select_findings(findings, "e de um")

    assert selected == findings
