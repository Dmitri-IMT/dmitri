from __future__ import annotations

# ruff: noqa: E501
import hashlib
import json
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Event, Thread
from urllib.error import URLError

import agent.targeted.web as web
import pytest
from agent.targeted.executor import ToolExecution
from agent.targeted.models import (
    TargetedGapReason,
    TargetedOutcome,
    TargetedTool,
    TargetedUnit,
)
from agent.targeted.web import (
    WEB_RESULT_POLICY_VERSION,
    WEB_RESULT_RULES,
    WEB_RESULT_SEEDS,
    WebBaseline,
    WebCandidate,
    WebResponse,
    classify_ffuf_candidate,
    parse_ffuf_json,
    parse_nikto_json,
    run_ffuf,
    run_nikto,
    validate_web_candidate,
)


def _unit() -> TargetedUnit:
    return TargetedUnit("192.0.2.10", 80, "tcp", "http", TargetedTool.FFUF, "http")


def test_ffuf_policy_is_versioned_and_parses_native_candidates() -> None:
    report = json.dumps(
        {"results": [{"url": "http://192.0.2.10:80/.env", "status": 200, "length": 12}]}
    )
    candidates = parse_ffuf_json(report, _unit())

    assert WEB_RESULT_POLICY_VERSION == "2026-09-15.1"
    assert len(WEB_RESULT_RULES) == 15
    assert candidates[0].path == "/.env"
    assert classify_ffuf_candidate(candidates[0]).rule_id == "WEB-SECRET-ENV-001"


def test_sensitive_response_is_redacted_and_wildcard_baseline_is_rejected() -> None:
    candidate = WebCandidate("http://192.0.2.10:80/.env", "/.env", 200)
    response = WebResponse(
        200,
        "text/plain",
        b"DB_USER=operator\nDB_PASSWORD=secret-value\n",
        candidate.url,
    )
    baseline = WebBaseline(404, "text/html", 9, 2, 1, "different")

    issue = validate_web_candidate(candidate, baseline, response=response)

    assert issue is not None
    assert issue.severity == "high"
    assert "secret-value" not in issue.evidence
    assert WEB_RESULT_POLICY_VERSION in issue.evidence
    assert (
        validate_web_candidate(
            candidate,
            WebBaseline(
                200, "text/plain", response.length, response.words, response.lines, "x"
            ),
            response=response,
        )
        is not None
    )
    digest = hashlib.sha256(re.sub(rb"\s+", b" ", response.body)).hexdigest()
    assert (
        validate_web_candidate(
            candidate,
            WebBaseline(
                200,
                "text/plain",
                response.length,
                response.words,
                response.lines,
                digest,
            ),
            response=response,
        )
        is None
    )


def test_admin_and_api_surfaces_are_observations() -> None:
    admin = WebCandidate("http://192.0.2.10:80/admin", "/admin", 200)
    api = WebCandidate("http://192.0.2.10:80/openapi.json", "/openapi.json", 200)
    admin_result = validate_web_candidate(
        admin,
        response=WebResponse(
            200,
            "text/html",
            b"<h1>Admin login</h1><form action='/admin/login'><input type=password></form>",
            admin.url,
        ),
    )
    api_result = validate_web_candidate(
        api,
        response=WebResponse(
            200, "application/json", b'{"openapi":"3.0.0","paths":{}}', api.url
        ),
    )

    assert admin_result.observation_key.startswith("web:administration")
    assert api_result.observation_key.startswith("web:api_surface")


def test_nikto_uses_only_supplied_pinned_database_rows() -> None:
    report = {
        "vulnerabilities": [
            {"id": "000123", "uri": "/config", "message": "safe detail"},
            {"id": "999999", "uri": "/ignored", "message": "unknown"},
        ]
    }
    issues = parse_nikto_json(report, _unit(), policy={"000123": "5"})

    assert len(issues) == 1
    assert issues[0].issue_key.startswith("nikto:000123")
    assert issues[0].severity == "high"


@pytest.mark.parametrize(
    ("path", "body", "rule_id", "severity"),
    [
        ("/.git/HEAD", b"ref: refs/heads/main\n", "WEB-VCS-GIT-001", "high"),
        (
            "/.git/config",
            b"[core]\nrepositoryformatversion = 0\n",
            "WEB-VCS-GIT-001",
            "high",
        ),
        (
            "/.svn/entries",
            b"<?xml version='1.0'?><wc-entries/>",
            "WEB-VCS-SVN-001",
            "high",
        ),
        ("/.svn/wc.db", b"SQLite format 3\x00", "WEB-VCS-SVN-001", "high"),
        (
            "/.env",
            b"DB_USER=operator\nDB_PASSWORD=secret\n",
            "WEB-SECRET-ENV-001",
            "high",
        ),
        (
            "/keys/id_rsa",
            b"-----BEGIN OPENSSH PRIVATE KEY-----\n",
            "WEB-SECRET-KEY-001",
            "critical",
        ),
        (
            "/config.json",
            b'{"database":"prod","password":"redacted"}',
            "WEB-CONFIG-001",
            "high",
        ),
        ("/backup.zip", b"PK\x03\x04 archive", "WEB-BACKUP-001", "high"),
        ("/database.sql", b"CREATE TABLE users (id int);", "WEB-DUMP-001", "high"),
        (
            "/error.log",
            b"2026-09-19 10:00:00 GET / HTTP/1.1\n2026-09-19 10:01:00 exception",
            "WEB-LOG-001",
            "medium",
        ),
        (
            "/phpinfo.php",
            b"PHP Version 8.3 phpinfo configuration",
            "WEB-DIAG-PHP-001",
            "medium",
        ),
        ("/server-status", b"Server Status\nrequests", "WEB-DIAG-SERVER-001", "medium"),
        (
            "/actuator/env",
            b'{"environment":{"propertySources":[]}}',
            "WEB-DIAG-ACTUATOR-001",
            "high",
        ),
        (
            "/prometheus",
            b"# HELP requests_total Requests\n# TYPE requests_total counter\nrequests_total 1",
            "WEB-METRICS-001",
            "medium",
        ),
        (
            "/assets/",
            b"<title>Index of /assets/</title><a href='a.txt'>a</a>",
            "WEB-DIRLIST-001",
            "medium",
        ),
        (
            "/admin",
            b"<h1>Admin login</h1><form action='/admin/login'><input type=password></form>",
            "WEB-ADMIN-001",
            None,
        ),
        ("/openapi.json", b'{"openapi":"3.0.0","paths":{}}', "WEB-API-DOCS-001", None),
    ],
)
def test_policy_matrix_requires_path_and_affirmative_signature(
    path: str, body: bytes, rule_id: str, severity: str | None
) -> None:
    candidate = WebCandidate(f"http://{_unit().ip}:{_unit().port}{path}", path, 200)
    result = validate_web_candidate(
        candidate,
        response=WebResponse(200, "text/plain", body, candidate.url),
    )

    assert result is not None
    assert result.evidence.startswith(f"{WEB_RESULT_POLICY_VERSION}:{rule_id}")
    if severity is None:
        assert result.observation_key.startswith("web:")
    else:
        assert result.severity == severity

    assert (
        validate_web_candidate(
            candidate,
            response=WebResponse(200, "text/html", b"not found", candidate.url),
        )
        is None
    )


def test_admin_arbitrary_form_is_not_an_observation() -> None:
    candidate = WebCandidate("http://192.0.2.10:80/admin", "/admin", 200)
    assert (
        validate_web_candidate(
            candidate,
            response=WebResponse(
                200, "text/html", b"<form><input type=password></form>", candidate.url
            ),
        )
        is None
    )


def test_policy_seeds_are_frozen_and_normalized() -> None:
    assert len(WEB_RESULT_RULES) == 15
    assert len(WEB_RESULT_SEEDS) == len(set(WEB_RESULT_SEEDS))
    assert all("/" not in seed[:1] for seed in WEB_RESULT_SEEDS)
    assert set(WEB_RESULT_SEEDS) >= {".env", ".git/HEAD", "openapi.json", "wp-admin"}
    assert WEB_RESULT_SEEDS == tuple(
        seed for rule in WEB_RESULT_RULES.values() for seed in rule.seeds
    )
    for rule in WEB_RESULT_RULES.values():
        assert callable(rule.matches_path)
        assert callable(rule.matches_body)
        assert rule.proof
        for seed in rule.seeds:
            classified = classify_ffuf_candidate(f"/{seed}")
            assert classified is not None
            assert classified.rule_id == rule.rule_id


def test_ffuf_parser_rejects_foreign_target_and_deduplicates() -> None:
    report = {
        "results": [
            {"url": "http://192.0.2.10:80/.env", "status": 200},
            {"url": "http://192.0.2.10:80/.env", "status": 200},
            {"url": "http://192.0.2.11:80/.env", "status": 200},
            {"url": "http://192.0.2.10:81/.env", "status": 200},
            {"url": "http://192.0.2.10:80/%2eenv?ignored=1#fragment", "status": 200},
        ]
    }

    candidates = parse_ffuf_json(report, _unit())

    assert [(candidate.path, candidate.status) for candidate in candidates] == [
        ("/.env", 200)
    ]


def test_directory_candidate_keeps_trailing_slash() -> None:
    candidates = parse_ffuf_json(
        {"results": [{"url": "http://192.0.2.10:80/assets/", "status": 200}]},
        _unit(),
    )
    assert candidates[0].path == "/assets/"
    assert classify_ffuf_candidate(candidates[0]).rule_id == "WEB-DIRLIST-001"


@pytest.mark.parametrize(
    "path", ["/application.properties.bak", "/config.json.old", "/web.config.save"]
)
def test_configuration_backup_variants_keep_configuration_rule(path: str) -> None:
    candidate = WebCandidate(f"http://192.0.2.10:80{path}", path, 200)
    assert classify_ffuf_candidate(candidate).rule_id == "WEB-CONFIG-001"


class _FakeExecutor:
    def __init__(self, execution: ToolExecution) -> None:
        self.execution = execution
        self.commands = []
        self.effective_entries = None

    def execute(self, command, **_deadline):
        self.commands.append(command)
        if len(command.argv) > 4 and command.argv[0] == "ffuf":
            self.effective_entries = (
                Path(command.argv[4]).read_text(encoding="utf-8").splitlines()
            )
        return self.execution


def _wordlist(tmp_path) -> str:
    path = tmp_path / "common.txt"
    path.write_text(
        "\n".join(f"base-{index}" for index in range(4_000)), encoding="utf-8"
    )
    return str(path)


def test_ffuf_argv_is_bounded_and_effective_wordlist_contains_policy_seeds(
    tmp_path,
) -> None:
    executor = _FakeExecutor(
        ToolExecution(
            TargetedOutcome.COMPLETED,
            exit_code=17,
            report=b'{"results": []}',
            report_present=True,
        )
    )

    result = run_ffuf(_unit(), executor, _wordlist(tmp_path), scan_id="scan-1")

    assert result.outcome == TargetedOutcome.COMPLETED
    assert result.exit_code == 17
    command = executor.commands[0]
    assert command.argv == [
        "ffuf",
        "-u",
        "http://192.0.2.10:80/FUZZ",
        "-w",
        command.argv[4],
        "-of",
        "json",
        "-o",
        "REPORT",
        "-noninteractive",
        "-s",
        "-ac",
        "-t",
        "2",
        "-rate",
        "20",
        "-timeout",
        "5",
        "-maxtime",
        "300",
    ]
    effective_entries = executor.effective_entries
    assert effective_entries is not None
    assert len(effective_entries) == 4_000 + len(WEB_RESULT_SEEDS)
    assert effective_entries == sorted(effective_entries)
    assert set(WEB_RESULT_SEEDS).issubset(effective_entries)
    assert "-k" not in command.argv
    assert not {"-recursion", "-e", "-H", "-X", "-request", "-proxy"}.intersection(
        command.argv
    )


def test_ffuf_https_accepts_self_signed_target_certificate(tmp_path) -> None:
    https_unit = TargetedUnit(
        "192.0.2.10", 443, "tcp", "https", TargetedTool.FFUF, "https"
    )
    executor = _FakeExecutor(
        ToolExecution(
            TargetedOutcome.COMPLETED,
            report=b'{"results": []}',
            report_present=True,
        )
    )

    result = run_ffuf(https_unit, executor, _wordlist(tmp_path))

    assert result.outcome == TargetedOutcome.COMPLETED
    assert executor.commands[0].argv[2] == "https://192.0.2.10:443/FUZZ"
    assert "-k" in executor.commands[0].argv


def test_ffuf_uses_one_baseline_and_at_most_32_validations(tmp_path) -> None:
    report = {
        "results": [
            {"url": f"http://192.0.2.10:80/backup-{index}.zip", "status": 200}
            for index in range(40)
        ]
    }
    executor = _FakeExecutor(
        ToolExecution(
            TargetedOutcome.COMPLETED,
            report=json.dumps(report).encode(),
            report_present=True,
        )
    )
    requested: list[str] = []

    def fetcher(url: str) -> WebResponse:
        requested.append(url)
        if ".dmitri-not-found-" in url:
            return WebResponse(404, "text/html", b"not found", url)
        return WebResponse(200, "application/zip", b"PK\x03\x04 archive", url)

    result = run_ffuf(
        _unit(), executor, _wordlist(tmp_path), scan_id="scan-1", fetcher=fetcher
    )

    assert result.outcome == TargetedOutcome.FAILED
    assert result.reason_code == TargetedGapReason.VALIDATION_LIMIT
    assert len(requested) == 33
    assert requested[0].startswith("http://192.0.2.10:80/.dmitri-not-found-")
    assert len(result.issues) == 32


def test_ffuf_validation_respects_stage_deadline(tmp_path) -> None:
    report = {
        "results": [
            {"url": f"http://192.0.2.10:80/backup-{index}.zip", "status": 200}
            for index in range(2)
        ]
    }
    executor = _FakeExecutor(
        ToolExecution(
            TargetedOutcome.COMPLETED,
            report=json.dumps(report).encode(),
            report_present=True,
        )
    )
    requested: list[str] = []

    def fetcher(url: str) -> WebResponse:
        requested.append(url)
        if ".dmitri-not-found-" in url:
            return WebResponse(404, "text/html", b"not found", url)
        if "backup-0" in url:
            import time

            time.sleep(0.25)
        return WebResponse(200, "application/zip", b"PK\x03\x04 archive", url)

    result = run_ffuf(
        _unit(),
        executor,
        _wordlist(tmp_path),
        scan_id="scan-1",
        fetcher=fetcher,
        stage_deadline=web.perf_counter() + 0.2,
    )

    assert result.outcome == TargetedOutcome.SKIPPED
    assert result.reason_code == TargetedGapReason.STAGE_BUDGET
    assert len(result.issues) == 1
    assert len(requested) == 2


def test_ffuf_baseline_failure_is_truthful_and_emits_no_results(tmp_path) -> None:
    executor = _FakeExecutor(
        ToolExecution(
            TargetedOutcome.COMPLETED,
            report=b'{"results": [{"url": "http://192.0.2.10:80/.env", "status": 200}]}',
            report_present=True,
        )
    )
    requested: list[str] = []

    def fetcher(url: str) -> WebResponse:
        requested.append(url)
        raise OSError("baseline unavailable")

    result = run_ffuf(
        _unit(), executor, _wordlist(tmp_path), scan_id="scan-1", fetcher=fetcher
    )

    assert result.outcome == TargetedOutcome.FAILED
    assert result.reason_code == TargetedGapReason.BASELINE_UNAVAILABLE
    assert len(requested) == 1


def test_ffuf_preserves_timeout_when_report_is_partial(tmp_path) -> None:
    executor = _FakeExecutor(
        ToolExecution(
            TargetedOutcome.TIMED_OUT,
            reason_code=TargetedGapReason.UNIT_TIMEOUT,
            report=b'{"results":[',
            report_present=True,
        )
    )

    result = run_ffuf(_unit(), executor, _wordlist(tmp_path))

    assert result.outcome == TargetedOutcome.TIMED_OUT
    assert result.reason_code == TargetedGapReason.UNIT_TIMEOUT
    assert result.issues == []


def test_ffuf_internal_max_runtime_marks_valid_report_timed_out(tmp_path) -> None:
    executor = _FakeExecutor(
        ToolExecution(
            TargetedOutcome.COMPLETED,
            exit_code=0,
            report=b'{"results": []}',
            report_present=True,
            diagnostic="Maximum running time for entire process reached, exiting.",
        )
    )

    result = run_ffuf(_unit(), executor, _wordlist(tmp_path))

    assert result.outcome == TargetedOutcome.TIMED_OUT
    assert result.reason_code == TargetedGapReason.UNIT_TIMEOUT


def test_ffuf_internal_max_runtime_preserves_validated_findings(tmp_path) -> None:
    executor = _FakeExecutor(
        ToolExecution(
            TargetedOutcome.COMPLETED,
            exit_code=0,
            report=b'{"results": [{"url": "http://192.0.2.10:80/.env", "status": 200}]}',
            report_present=True,
            stdout=b"Maximum running time for entire process reached, exiting.",
        )
    )

    def fetcher(url: str) -> WebResponse:
        if ".dmitri-not-found-" in url:
            return WebResponse(404, "text/html", b"not found", url)
        return WebResponse(
            200, "text/plain", b"DB_USER=operator\nDB_PASSWORD=secret\n", url
        )

    result = run_ffuf(_unit(), executor, _wordlist(tmp_path), fetcher=fetcher)

    assert result.outcome == TargetedOutcome.TIMED_OUT
    assert result.reason_code == TargetedGapReason.UNIT_TIMEOUT
    assert len(result.issues) == 1


def test_ffuf_internal_max_runtime_keeps_stage_budget_precedence(tmp_path) -> None:
    executor = _FakeExecutor(
        ToolExecution(
            TargetedOutcome.COMPLETED,
            report=b'{"results": []}',
            report_present=True,
            stderr=b"Maximum running time for entire process reached, exiting.",
        )
    )

    result = run_ffuf(
        _unit(),
        executor,
        _wordlist(tmp_path),
        stage_deadline=web.perf_counter() - 1,
    )

    assert result.outcome == TargetedOutcome.SKIPPED
    assert result.reason_code == TargetedGapReason.STAGE_BUDGET


def test_ffuf_internal_max_runtime_keeps_cancel_precedence(tmp_path) -> None:
    executor = _FakeExecutor(
        ToolExecution(
            TargetedOutcome.COMPLETED,
            report=b'{"results": []}',
            report_present=True,
            diagnostic="Maximum running time for entire process reached, exiting.",
        )
    )
    cancel_event = Event()
    cancel_event.set()

    result = run_ffuf(_unit(), executor, _wordlist(tmp_path), cancel_event=cancel_event)

    assert result.outcome == TargetedOutcome.SKIPPED
    assert result.reason_code == TargetedGapReason.SCAN_CANCELLED


@pytest.mark.parametrize("report", [b'{"results": {}}', b'{"results": "bad"}'])
def test_ffuf_non_list_results_are_malformed(tmp_path, report: bytes) -> None:
    executor = _FakeExecutor(
        ToolExecution(TargetedOutcome.COMPLETED, report=report, report_present=True)
    )
    result = run_ffuf(_unit(), executor, _wordlist(tmp_path), scan_id="scan-1")
    assert result.outcome == TargetedOutcome.FAILED
    assert result.reason_code == TargetedGapReason.MALFORMED_REPORT


def test_ffuf_truncated_baseline_is_unavailable(tmp_path) -> None:
    executor = _FakeExecutor(
        ToolExecution(
            TargetedOutcome.COMPLETED,
            report=b'{"results": [{"url": "http://192.0.2.10:80/.env", "status": 200}]}',
            report_present=True,
        )
    )

    def fetcher(url: str) -> WebResponse:
        return WebResponse(404, "text/html", b"not found", url, truncated=True)

    result = run_ffuf(
        _unit(), executor, _wordlist(tmp_path), scan_id="scan-1", fetcher=fetcher
    )
    assert result.outcome == TargetedOutcome.FAILED
    assert result.reason_code == TargetedGapReason.BASELINE_UNAVAILABLE


def test_web_validation_rejects_baseline_and_external_redirect() -> None:
    candidate = WebCandidate("http://192.0.2.10:80/.env", "/.env", 200)
    response = WebResponse(200, "text/plain", b"A=1\nB=2\n", candidate.url)
    baseline = WebBaseline(
        200,
        "text/plain",
        response.length,
        response.words,
        response.lines,
        hashlib.sha256(re.sub(rb"\s+", b" ", response.body)).hexdigest(),
    )

    assert validate_web_candidate(candidate, baseline, response=response) is None
    assert (
        validate_web_candidate(
            candidate,
            response=WebResponse(
                200, "text/plain", b"A=1\nB=2\n", "http://evil.example/.env"
            ),
        )
        is None
    )


class _RedirectResponse:
    def __init__(self, status: int, headers: dict[str, str], body: bytes = b"") -> None:
        self.status = status
        self.headers = headers
        self._body = body

    def getcode(self) -> int:
        return self.status

    def read(self, _limit: int) -> bytes:
        return self._body

    def close(self) -> None:
        pass


def test_fetch_disables_certificate_verification_only_for_https(monkeypatch) -> None:
    import ssl

    captured: list[object] = []

    class Opener:
        def open(self, _request, timeout: float):
            return _RedirectResponse(200, {"Content-Type": "text/plain"}, b"ok")

    def build(*handlers):
        captured.extend(handlers)
        return Opener()

    monkeypatch.setattr(web, "build_opener", build)

    web._fetch("https://192.0.2.10:443/")

    https_handler = next(
        handler for handler in captured if isinstance(handler, web.HTTPSHandler)
    )
    assert https_handler._context.verify_mode == ssl.CERT_NONE
    assert https_handler._context.check_hostname is False


def test_fetch_follows_at_most_two_same_origin_redirects() -> None:
    seen: list[str] = []
    responses = iter(
        [
            _RedirectResponse(302, {"Location": "/one"}),
            _RedirectResponse(302, {"Location": "/two"}),
            _RedirectResponse(200, {"Content-Type": "text/plain"}, b"ok"),
        ]
    )

    def opener(request, timeout: float):
        seen.append(request.full_url)
        return next(responses)

    result = web._fetch("http://192.0.2.10:80/start", opener=opener)
    assert result.url == "http://192.0.2.10:80/two"
    assert len(seen) == 3


def test_fetch_rejects_external_redirect() -> None:
    def opener(_request, timeout: float):
        return _RedirectResponse(302, {"Location": "https://evil.example/"})

    with pytest.raises(URLError):
        web._fetch("http://192.0.2.10:80/start", opener=opener)


@pytest.mark.parametrize("status", [404, 401, 403])
def test_fetch_returns_bounded_http_error_responses_from_local_server(
    status: int,
) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            body = f"local status {status}".encode()
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args: object) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        response = web._fetch(f"http://127.0.0.1:{server.server_port}/status")
    finally:
        server.shutdown()
        thread.join()
        server.server_close()

    assert response.status == status
    assert response.content_type == "text/plain"
    assert response.body == f"local status {status}".encode()
    assert response.truncated is False


def test_nikto_parser_requires_pinned_id_and_maps_highest_category() -> None:
    report = {
        "vulnerabilities": [
            {"id": "123", "uri": "/a", "message": "default file"},
            {"id": "124", "uri": "/b", "message": "command", "category": "8c"},
            {"id": "125", "uri": "/c", "message": "ignored", "category": "0"},
            {"id": "126", "uri": "/d", "message": "not pinned", "category": "5"},
        ]
    }

    issues = parse_nikto_json(report, _unit(), policy={"000123": "2", "000124": "8c"})

    assert [(issue.issue_key, issue.severity) for issue in issues] == [
        ("nikto:000123:/a", "medium"),
        ("nikto:000124:/b", "critical"),
    ]
    assert "default file" in issues[0].evidence
    assert "not pinned" not in " ".join(issue.evidence for issue in issues)


def test_nikto_parser_bounds_issue_key_for_long_uri() -> None:
    long_uri = "/" + "a" * 600
    issues = parse_nikto_json(
        {"vulnerabilities": [{"id": "123", "uri": long_uri, "message": "finding"}]},
        _unit(),
        policy={"000123": "5"},
    )

    assert len(issues) == 1
    assert len(issues[0].issue_key) == 256
    assert issues[0].issue_key.startswith("nikto:000123:/")


def test_nikto_parser_accepts_native_host_array_report() -> None:
    report = [
        {
            "host": "192.0.2.10",
            "ip": "192.0.2.10",
            "port": 80,
            "vulnerabilities": [
                {
                    "id": "750500",
                    "method": "GET",
                    "msg": "Directory indexing found.",
                    "url": "/admin/",
                }
            ],
        }
    ]

    issues = parse_nikto_json(json.dumps(report), _unit(), policy={"750500": "5"})

    assert len(issues) == 1
    assert issues[0].issue_key == "nikto:750500:/admin/"
    assert "Directory indexing found" in issues[0].description


def test_nikto_target_matching_ignores_foreign_host_or_port() -> None:
    report = {
        "vulnerabilities": [
            {
                "id": "123",
                "host": "192.0.2.10",
                "port": 80,
                "uri": "/ok",
                "message": "ok",
            },
            {
                "id": "123",
                "host": "192.0.2.11",
                "port": 80,
                "uri": "/host",
                "message": "host",
            },
            {
                "id": "123",
                "host": "192.0.2.10",
                "port": 81,
                "uri": "/port",
                "message": "port",
            },
        ]
    }

    issues = parse_nikto_json(report, _unit(), policy={"000123": "5"})

    assert [issue.issue_key for issue in issues] == ["nikto:000123:/ok"]


def test_nikto_valid_nonzero_exit_is_completed_and_redacts_secrets() -> None:
    report = {
        "vulnerabilities": [
            {
                "id": "123",
                "uri": "/config",
                "message": "password=secret-value token=abc",
            }
        ]
    }
    executor = _FakeExecutor(
        ToolExecution(
            TargetedOutcome.COMPLETED,
            exit_code=7,
            report=json.dumps(report).encode(),
            report_present=True,
        )
    )

    result = run_nikto(_unit(), executor, policy={"000123": "5"})

    assert result.outcome == TargetedOutcome.COMPLETED
    assert result.exit_code == 7
    assert len(result.issues) == 1
    assert "secret-value" not in result.issues[0].evidence
    assert "abc" not in result.issues[0].evidence
    assert result.issues[0].evidence.startswith(
        f"{WEB_RESULT_POLICY_VERSION}:nikto:000123"
    )
    assert executor.commands[0].argv == [
        "nikto",
        "-h",
        "http://192.0.2.10:80",
        "-nointeractive",
        "-nolookup",
        "-nocheck",
        "-nocookies",
        "-Tuning",
        "2345789acf",
        "-timeout",
        "5",
        "-maxtime",
        "200s",
        "-Pause",
        "0.2",
        "-Format",
        "json",
        "-output",
        "REPORT",
    ]
    assert executor.commands[0].report_path_mode == "base"


@pytest.mark.parametrize("report", [b"not-json", b"{}", b'{"vulnerabilities": {}}'])
def test_nikto_missing_or_malformed_report_is_failed(report: bytes) -> None:
    executor = _FakeExecutor(
        ToolExecution(
            TargetedOutcome.COMPLETED,
            exit_code=9,
            report=report,
            report_present=True,
        )
    )

    result = run_nikto(_unit(), executor, policy={"000123": "5"})

    assert result.outcome == TargetedOutcome.FAILED
    assert result.reason_code == TargetedGapReason.MALFORMED_REPORT


def test_nikto_valid_zero_issue_report_is_completed() -> None:
    executor = _FakeExecutor(
        ToolExecution(
            TargetedOutcome.COMPLETED,
            exit_code=1,
            report=b'{"vulnerabilities": []}',
            report_present=True,
        )
    )

    result = run_nikto(_unit(), executor, policy={"000123": "5"})

    assert result.outcome == TargetedOutcome.COMPLETED
    assert result.issues == []


def test_nikto_missing_report_is_failed_even_when_exit_is_nonzero() -> None:
    executor = _FakeExecutor(
        ToolExecution(
            TargetedOutcome.COMPLETED,
            exit_code=9,
            report_present=False,
        )
    )

    result = run_nikto(_unit(), executor, policy={"000123": "5"})

    assert result.outcome == TargetedOutcome.FAILED
    assert result.reason_code == TargetedGapReason.MALFORMED_REPORT


def test_nikto_preserves_timeout_when_report_is_partial() -> None:
    executor = _FakeExecutor(
        ToolExecution(
            TargetedOutcome.TIMED_OUT,
            reason_code=TargetedGapReason.UNIT_TIMEOUT,
            report=b"[",
            report_present=True,
        )
    )

    result = run_nikto(_unit(), executor, policy={"000123": "5"})

    assert result.outcome == TargetedOutcome.TIMED_OUT
    assert result.reason_code == TargetedGapReason.UNIT_TIMEOUT


def test_nikto_internal_time_limit_marks_valid_partial_report_as_timed_out() -> None:
    executor = _FakeExecutor(
        ToolExecution(
            TargetedOutcome.COMPLETED,
            exit_code=0,
            diagnostic="+ ERROR: Host maximum execution time of 150 seconds reached",
            report=json.dumps(
                {
                    "vulnerabilities": [
                        {"id": "123", "uri": "/config", "message": "issue"}
                    ]
                }
            ).encode(),
            report_present=True,
        )
    )

    result = run_nikto(_unit(), executor, policy={"000123": "5"})

    assert result.outcome == TargetedOutcome.TIMED_OUT
    assert result.reason_code == TargetedGapReason.UNIT_TIMEOUT
    assert [issue.issue_key for issue in result.issues] == ["nikto:000123:/config"]


def test_nikto_issue_limit_is_truthful() -> None:
    report = {
        "vulnerabilities": [
            {"id": str(index), "uri": f"/item-{index}", "message": "issue"}
            for index in range(1, 130)
        ]
    }
    policy = {str(index).zfill(6): "5" for index in range(1, 130)}
    executor = _FakeExecutor(
        ToolExecution(
            TargetedOutcome.COMPLETED,
            report=json.dumps(report).encode(),
            report_present=True,
        )
    )
    result = run_nikto(_unit(), executor, policy=policy)
    assert result.outcome == TargetedOutcome.FAILED
    assert result.reason_code == TargetedGapReason.ISSUE_LIMIT
    assert len(result.issues) == 128


def test_nikto_policy_preflight_requires_pinned_sha256(tmp_path, monkeypatch) -> None:
    db_tests = tmp_path / "db_tests"
    db_tests.write_text("id,tuning\n123,5\n", encoding="utf-8")
    monkeypatch.setattr(web, "NIKTO_DB_TESTS_PATH", db_tests)
    monkeypatch.setattr(
        web, "NIKTO_DB_TESTS_SHA256", hashlib.sha256(db_tests.read_bytes()).hexdigest()
    )
    executor = _FakeExecutor(
        ToolExecution(
            TargetedOutcome.COMPLETED,
            report=b'{"vulnerabilities": [{"id": "123", "uri": "/config", "message": "issue"}]}',
            report_present=True,
        )
    )
    result = run_nikto(_unit(), executor)
    assert result.outcome == TargetedOutcome.COMPLETED
    assert len(result.issues) == 1

    db_tests.write_text("id,tuning\n123,8\n", encoding="utf-8")
    result = run_nikto(_unit(), executor)
    assert result.outcome == TargetedOutcome.SKIPPED
    assert result.reason_code == TargetedGapReason.POLICY_UNAVAILABLE


def test_nikto_policy_reads_pinned_database_csv_with_comment_preamble(
    tmp_path, monkeypatch
) -> None:
    db_tests = tmp_path / "db_tests"
    db_tests.write_text(
        '# preamble\n"000123","CVE-2026-1234","5","/config","GET",'
        '"CODE:200","exposed configuration","",""\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(web, "NIKTO_DB_TESTS_PATH", db_tests)
    monkeypatch.setattr(
        web, "NIKTO_DB_TESTS_SHA256", hashlib.sha256(db_tests.read_bytes()).hexdigest()
    )
    executor = _FakeExecutor(
        ToolExecution(
            TargetedOutcome.COMPLETED,
            report=json.dumps(
                {
                    "vulnerabilities": [
                        {"id": "000123", "uri": "/config", "message": "issue"}
                    ]
                }
            ).encode(),
            report_present=True,
        )
    )

    result = run_nikto(_unit(), executor)

    assert result.outcome == TargetedOutcome.COMPLETED
    assert result.issues[0].issue_key == "nikto:000123:/config"


def test_nikto_retains_method_and_only_safe_references() -> None:
    report = {
        "vulnerabilities": [
            {
                "id": "123",
                "method": "GET",
                "uri": "/config",
                "message": "safe detail",
                "references": [
                    "https://vendor.example/advisory/123",
                    "CVE-2026-1234",
                    "file:///private/report",
                ],
            }
        ]
    }
    issue = parse_nikto_json(report, _unit(), policy={"000123": "5"})[0]
    assert "method=GET" in issue.evidence
    assert issue.cve_id == "CVE-2026-1234"
    assert issue.references == ["https://vendor.example/[REDACTED]"]


def test_ffuf_startup_failure_preserves_sanitized_diagnostic(tmp_path) -> None:
    executor = _FakeExecutor(
        ToolExecution(
            TargetedOutcome.COMPLETED,
            exit_code=1,
            diagnostic="Cannot read configuration directory: permission denied",
        )
    )

    result = run_ffuf(_unit(), executor, _wordlist(tmp_path))

    assert result.outcome == TargetedOutcome.FAILED
    assert result.reason_code == TargetedGapReason.EXECUTION_ERROR
    assert "permission denied" in result.diagnostic


def test_nikto_stdout_time_limit_preserves_partial_findings() -> None:
    executor = _FakeExecutor(
        ToolExecution(
            TargetedOutcome.COMPLETED,
            exit_code=0,
            report=b'{"vulnerabilities": [{"id":"000123","uri":"/config","msg":"configuration exposed"}]}',
            report_present=True,
            stdout=b"+ Host maximum execution time of 200 seconds reached",
        )
    )

    result = run_nikto(_unit(), executor, policy={"000123": "5"})

    assert result.outcome == TargetedOutcome.TIMED_OUT
    assert result.reason_code == TargetedGapReason.UNIT_TIMEOUT
    assert len(result.issues) == 1


def test_nikto_error_limit_preserves_partial_findings() -> None:
    executor = _FakeExecutor(
        ToolExecution(
            TargetedOutcome.COMPLETED,
            exit_code=0,
            report=b'{"vulnerabilities": [{"id":"000123","uri":"/config","msg":"configuration exposed"}]}',
            report_present=True,
            stdout=(
                b"+ ERROR: *** Error limit (20) reached for host, giving up. "
                b"Last error: error reading HTTP response. ***"
            ),
        )
    )

    result = run_nikto(_unit(), executor, policy={"000123": "5"})

    assert result.outcome == TargetedOutcome.FAILED
    assert result.reason_code == TargetedGapReason.EXECUTION_ERROR
    assert len(result.issues) == 1


def test_nikto_benign_error_advisory_does_not_fail_execution() -> None:
    executor = _FakeExecutor(
        ToolExecution(
            TargetedOutcome.COMPLETED,
            exit_code=0,
            report=b'{"vulnerabilities": []}',
            report_present=True,
            stderr=b"+ ERROR: TLS fingerprinting advisory is unavailable.",
        )
    )

    result = run_nikto(_unit(), executor, policy={"000123": "5"})

    assert result.outcome == TargetedOutcome.COMPLETED
