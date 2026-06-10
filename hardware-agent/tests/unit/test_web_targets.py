from __future__ import annotations

import json
from pathlib import Path

from agent.config import AgentSettings
from agent.scanner.models import HostInfo, PortInfo, ServiceInfo
from agent.tools.runner import ToolRunResult, ToolRunStatus
from agent.tools.web import (
    parse_ffuf_results,
    parse_nikto_output,
    run_web_security_tools,
    select_web_targets,
)


class _FakeToolRunner:
    def run(self, executable: str, arguments: list[str]) -> ToolRunResult:
        if executable == "ffuf":
            return ToolRunResult(
                tool=executable,
                argv=[executable, *arguments],
                status=ToolRunStatus.COMPLETED,
                exit_code=0,
                stdout=json.dumps(
                    {
                        "results": [
                            {
                                "url": "http://192.168.1.60:80/.git/",
                                "status": 403,
                                "length": 123,
                            },
                            {
                                "url": "http://192.168.1.60:80/assets/",
                                "status": 200,
                                "length": 999,
                            }
                        ]
                    }
                ),
            )
        if executable == "nikto":
            return ToolRunResult(
                tool=executable,
                argv=[executable, *arguments],
                status=ToolRunStatus.COMPLETED,
                exit_code=0,
                stdout="+ /admin/: Admin login page/section found.",
            )
        raise AssertionError(f"Unexpected tool: {executable}")


def test_select_web_targets_uses_open_http_ports_from_nmap_data() -> None:
    host = HostInfo(
        ip="192.168.1.20",
        hostname="web.local",
        ports=[
            PortInfo(port=22, service=ServiceInfo(name="ssh")),
            PortInfo(port=80, service=ServiceInfo(name="http")),
            PortInfo(port=443, service=ServiceInfo(name="https")),
            PortInfo(port=8080, state="filtered", service=ServiceInfo(name="http")),
        ],
    )

    targets = select_web_targets([host])

    assert [target.url for target in targets] == [
        "http://192.168.1.20:80",
        "https://192.168.1.20:443",
    ]
    assert [target.port.port for target in targets] == [80, 443]


def test_select_web_targets_uses_detected_service_on_nonstandard_ports() -> None:
    host = HostInfo(
        ip="192.168.1.30",
        hostname="appliance.local",
        ports=[
            PortInfo(port=7001, service=ServiceInfo(name="http")),
            PortInfo(port=7443, service=ServiceInfo(name="https")),
            PortInfo(port=3128, service=ServiceInfo(name="http-proxy")),
        ],
    )

    targets = select_web_targets([host])

    assert [target.url for target in targets] == [
        "http://192.168.1.30:7001",
        "https://192.168.1.30:7443",
        "http://192.168.1.30:3128",
    ]


def test_parse_ffuf_results_classifies_all_discovered_paths() -> None:
    host = HostInfo(
        ip="192.168.1.40",
        hostname="web.local",
        ports=[PortInfo(port=80, service=ServiceInfo(name="http"))],
    )
    target = select_web_targets([host])[0]
    raw_json = """
    {
      "results": [
        {"url": "http://192.168.1.40:80/.git/", "status": 403, "length": 123},
        {"url": "http://192.168.1.40:80/assets/", "status": 200, "length": 999}
      ]
    }
    """

    hits = parse_ffuf_results(target, raw_json)

    assert [hit.path for hit in hits] == ["/.git/", "/assets/"]
    assert [hit.status for hit in hits] == [403, 200]
    assert [hit.dangerous for hit in hits] == [True, False]
    assert [hit.risk for hit in hits] == ["dangerous", "informational"]


def test_parse_nikto_output_keeps_reported_web_issues() -> None:
    host = HostInfo(
        ip="192.168.1.50",
        hostname="web.local",
        ports=[PortInfo(port=80, service=ServiceInfo(name="http"))],
    )
    target = select_web_targets([host])[0]
    output = """
    - Nikto v2.5.0
    + Target IP:          192.168.1.50
    + Server: Apache
    + /admin/: Admin login page/section found.
    + OSVDB-3092: /backup/: This might be interesting.
    + 1 host(s) tested
    """

    issues = parse_nikto_output(target, output)

    assert [issue.path for issue in issues] == ["/admin/", "/backup/"]
    assert issues[0].title == "Nikto reported /admin/"
    assert issues[1].title == "Nikto reported OSVDB-3092"


def test_parse_nikto_output_keeps_header_security_issues() -> None:
    host = HostInfo(
        ip="192.168.1.51",
        hostname="web.local",
        ports=[PortInfo(port=443, service=ServiceInfo(name="https"))],
    )
    target = select_web_targets([host])[0]
    output = (
        "+ The anti-clickjacking X-Frame-Options header is not present.\n"
        "+ 1 host(s) tested"
    )

    issues = parse_nikto_output(target, output)

    assert len(issues) == 1
    assert issues[0].title == (
        "Nikto reported The anti-clickjacking X-Frame-Options header is not present"
    )
    assert issues[0].path is None


def test_run_web_security_tools_attaches_tool_scripts(
    tmp_path: Path,
) -> None:
    wordlist = tmp_path / "web.txt"
    wordlist.write_text("admin\n.git\n", encoding="utf-8")
    host = HostInfo(
        ip="192.168.1.60",
        hostname="web.local",
        ports=[PortInfo(port=80, service=ServiceInfo(name="http"))],
    )
    settings = AgentSettings(
        scan_mode="extensive",
        web_wordlist_path=str(wordlist),
    )

    summary = run_web_security_tools(
        [host],
        settings,
        tool_runner=_FakeToolRunner(),
    )

    assert summary.targets_discovered == 1
    assert summary.tools_attempted == 2
    assert summary.finding_candidates == 3
    assert [script.script_id for script in host.ports[0].scripts] == ["ffuf", "nikto"]
    ffuf_hits = host.ports[0].scripts[0].data["hits"]
    assert [hit["path"] for hit in ffuf_hits] == ["/.git/", "/assets/"]
    assert [hit["dangerous"] for hit in ffuf_hits] == [True, False]


def test_run_web_security_tools_is_disabled_for_quick_by_default(
    tmp_path: Path,
) -> None:
    wordlist = tmp_path / "web.txt"
    wordlist.write_text("admin\n", encoding="utf-8")
    host = HostInfo(
        ip="192.168.1.61",
        hostname="web.local",
        ports=[PortInfo(port=80, service=ServiceInfo(name="http"))],
    )

    summary = run_web_security_tools(
        [host],
        AgentSettings(scan_mode="quick", web_wordlist_path=str(wordlist)),
        tool_runner=_FakeToolRunner(),
    )

    assert summary.targets_discovered == 1
    assert summary.tools_attempted == 0
    assert host.ports[0].scripts == []
