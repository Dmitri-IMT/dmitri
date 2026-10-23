from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from api.models.persistence import (
    AIFixRecord,
    CPERecord,
    KevRecord,
    PortRecord,
    ServiceRecord,
)
from api.schemas.ai import ProviderCVEFixResearch, ProviderFixOption
from api.services.ai.context import build_scan_ai_context
from api.services.ai.openai_responses import AIProviderError
from api.services.ai.research import (
    attach_cached_fix_records,
    attach_fix_records,
    clean_source_url,
    sourced_fix_record,
)
from read_factories import (
    make_finding,
    make_host,
    make_org,
    make_scan,
    make_scan_host,
)
from sqlmodel import select

SETTINGS = SimpleNamespace(
    ai_fix_record_ttl_fixed_days=14, ai_fix_record_ttl_unfixed_days=2
)
ADVISORY = "https://www.openssh.com/releasenotes.html"


def _option(**overrides) -> ProviderFixOption:
    values = {
        "effort": "update",
        "who": "it_person",
        "steps": ["Install OpenSSH 9.3p2 from the vendor packages."],
        "fixed_version": "9.3p2",
        "fixes_fully": True,
        "source_name": "OpenSSH release notes",
        "source_url": f"{ADVISORY}?utm_source=openai",
    }
    values.update(overrides)
    return ProviderFixOption(**values)


def _research(*options: ProviderFixOption) -> ProviderCVEFixResearch:
    return ProviderCVEFixResearch(version_affected="yes", options=list(options))


class _Provider:
    def __init__(self, results):
        self.results = results
        self.targets = []

    def research_fix(self, target):
        self.targets.append(target)
        result = self.results[target.cve_id]
        if isinstance(result, Exception):
            raise result
        return result


def _scan(session, cves=("CVE-2026-0001",)):
    org = make_org(session, "Research Org")
    scan = make_scan(session, org.id)
    host = make_host(session, org.id, "192.168.1.10")
    scan_host = make_scan_host(session, scan.scan_id, host.id, "192.168.1.10")
    for index, cve_id in enumerate(cves):
        port = PortRecord(
            scan_host_id=scan_host.id, port=22 + index, protocol="tcp", state="open"
        )
        session.add(port)
        session.flush()
        session.add(
            ServiceRecord(port_id=port.id, name="ssh", version="OpenSSH 9.2p1 Debian")
        )
        session.add(CPERecord(port_id=port.id, cpe="cpe:/a:openbsd:openssh:9.2p1"))
        finding = make_finding(session, scan.scan_id, scan_host.id, f"research-{index}")
        finding.cve_id = cve_id
        finding.port_id = port.id
        session.add(finding)
    session.commit()
    return scan


def _attach(session, scan, provider, now):
    context = build_scan_ai_context(session, scan)
    attach_fix_records(session, context, provider, settings=SETTINGS, now=now)
    return context


def test_sourced_options_are_saved_and_attached(administrative_session):
    scan = _scan(administrative_session)
    provider = _Provider(
        {
            "CVE-2026-0001": (
                _research(
                    _option(source_url="https://forum.example.com/thread"),
                    _option(),
                ),
                {ADVISORY + "?utm_source=openai", "https://other.example.com/"},
            )
        }
    )
    now = datetime.now(timezone.utc)

    context = _attach(administrative_session, scan, provider, now)

    assert [target.product for target in provider.targets] == ["openbsd openssh"]
    assert provider.targets[0].version == "9.2p1"
    assert provider.targets[0].service == "ssh"
    finding = context.top_findings[0]
    assert finding.version_affected == "yes"
    assert [option.source_name for option in finding.fix_options] == [
        "OpenSSH release notes"
    ]
    assert [source.url for source in finding._fix_sources] == [ADVISORY]
    row = administrative_session.exec(select(AIFixRecord)).one()
    assert row.cve_id == "CVE-2026-0001"
    assert row.has_fix is True
    assert row.expires_at == now + timedelta(days=14)
    assert row.record_json["options"][0]["source_url"] == ADVISORY


def test_current_record_is_reused_until_kev_or_expiry_changes(
    administrative_session,
):
    scan = _scan(administrative_session)
    provider = _Provider({"CVE-2026-0001": (_research(_option()), {ADVISORY})})
    now = datetime.now(timezone.utc)

    _attach(administrative_session, scan, provider, now)
    context = _attach(administrative_session, scan, provider, now)
    assert len(provider.targets) == 1
    assert context.top_findings[0].fix_options

    administrative_session.add(
        KevRecord(cve_id="CVE-2026-0001", required_action="Apply updates.")
    )
    administrative_session.commit()
    _attach(administrative_session, scan, provider, now)
    assert len(provider.targets) == 2
    assert provider.targets[1].kev_required_action == "Apply updates."

    _attach(administrative_session, scan, provider, now + timedelta(days=15))
    assert len(provider.targets) == 3
    assert len(administrative_session.exec(select(AIFixRecord)).all()) == 1


def test_record_without_a_consulted_source_is_not_saved(administrative_session):
    scan = _scan(administrative_session)
    provider = _Provider({"CVE-2026-0001": (_research(_option()), set())})

    now = datetime.now(timezone.utc)
    context = _attach(administrative_session, scan, provider, now)

    assert context.top_findings[0].fix_options == []
    assert administrative_session.exec(select(AIFixRecord)).all() == []


def test_rate_limit_stops_the_job_after_saving_other_records(administrative_session):
    scan = _scan(administrative_session, ("CVE-2026-0001", "CVE-2026-0002"))
    provider = _Provider(
        {
            "CVE-2026-0001": (_research(_option()), {ADVISORY}),
            "CVE-2026-0002": AIProviderError(
                "provider_rate_limited", retryable=True, retry_after_seconds=30
            ),
        }
    )

    with pytest.raises(AIProviderError) as raised:
        _attach(administrative_session, scan, provider, datetime.now(timezone.utc))

    assert raised.value.code == "provider_rate_limited"
    rows = administrative_session.exec(select(AIFixRecord)).all()
    assert [row.cve_id for row in rows] == ["CVE-2026-0001"]


def test_other_provider_errors_skip_only_that_vulnerability(administrative_session):
    scan = _scan(administrative_session)
    provider = _Provider(
        {"CVE-2026-0001": AIProviderError("provider_timeout", retryable=True)}
    )

    now = datetime.now(timezone.utc)
    context = _attach(administrative_session, scan, provider, now)

    assert context.top_findings[0].fix_options == []


def test_sourced_fix_record_cleans_text_and_puts_the_easiest_full_fix_first():
    record = sourced_fix_record(
        _research(
            _option(effort="workaround", fixes_fully=False),
            _option(
                effort="update",
                steps=[
                    "Install **9.3p2** ([openssh.com](https://www.openssh.com/x)).",
                    "See [the notes](https://www.openssh.com/y) https://a.example/z",
                ],
            ),
        ),
        {ADVISORY},
    )

    assert record is not None
    assert [option["effort"] for option in record["options"]] == [
        "update",
        "workaround",
    ]
    assert record["options"][0]["steps"] == ["Install 9.3p2.", "See the notes"]


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://Vendor.example.com/a?utm_source=openai&id=1#top",
            "https://vendor.example.com/a?id=1",
        ),
        ("javascript:alert(1)", None),
        ("ftp://vendor.example.com/a", None),
    ],
)
def test_clean_source_url(url, expected):
    assert clean_source_url(url) == expected


def test_chat_reads_current_records_without_researching(administrative_session):
    scan = _scan(administrative_session)
    now = datetime.now(timezone.utc)
    _attach(
        administrative_session,
        scan,
        _Provider({"CVE-2026-0001": (_research(_option()), {ADVISORY})}),
        now,
    )
    context = build_scan_ai_context(administrative_session, scan)
    assert context.top_findings[0].fix_options == []

    attach_cached_fix_records(administrative_session, context.top_findings, now=now)

    assert context.top_findings[0].product == "openbsd openssh"
    assert [option.fixed_version for option in context.top_findings[0].fix_options] == [
        "9.3p2"
    ]
