from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path
from urllib import error, request


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run backend smoke test with one command."
    )
    parser.add_argument(
        "--skip-checks",
        action="store_true",
        help="Skip ruff and pytest before starting the stack.",
    )
    parser.add_argument(
        "--keep-up",
        action="store_true",
        help="Keep docker compose services running after the smoke test.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=90,
        help="Timeout for API readiness and worker processing.",
    )
    args = parser.parse_args()

    backend_dir = Path(__file__).resolve().parents[2]
    repo_root = backend_dir.parent
    payload_path = repo_root / "contracts" / "examples" / "scan_result.example.json"
    api_base_url = _get_api_base_url(backend_dir)

    if not args.skip_checks:
        _run(["python", "-m", "ruff", "check", "."], cwd=backend_dir)
        _run(["python", "-m", "pytest"], cwd=backend_dir)

    try:
        _run(
            [
                "docker",
                "compose",
                "up",
                "-d",
                "--build",
                "postgres",
                "backend",
                "worker",
            ],
            cwd=backend_dir,
        )
        _wait_for_health(f"{api_base_url}/api/v1/health", args.timeout_seconds)

        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        ingest_response = _post_json(f"{api_base_url}/api/v1/scans", payload)
        scan_id = ingest_response["scan_id"]

        detail_before = _get_json(f"{api_base_url}/api/v1/scans/{scan_id}")
        jobs_before = detail_before["enrichment_jobs"]
        if not jobs_before:
            raise RuntimeError("Smoke test failed: no enrichment jobs were created.")
        if any(job["status"] != "pending" for job in jobs_before):
            raise RuntimeError(
                "Smoke test failed: jobs should be pending immediately after ingestion."
            )

        detail_after = _wait_for_jobs(api_base_url, scan_id, args.timeout_seconds)
        findings = _get_json(f"{api_base_url}/api/v1/findings")

        if not any(
            job["status"] == "completed"
            for job in detail_after["enrichment_jobs"]
        ):
            raise RuntimeError("Smoke test failed: worker did not complete any jobs.")
        if not any(
            finding["confidence"] == "confirmed" and "nvd" in finding["source_labels"]
            for finding in findings
        ):
            raise RuntimeError(
                "Smoke test failed: findings were not enriched by the worker."
            )

        print(f"Smoke test passed for scan {scan_id}.")
        return 0
    finally:
        if not args.keep_up:
            _run(["docker", "compose", "down"], cwd=backend_dir, check=False)


def _wait_for_jobs(
    api_base_url: str,
    scan_id: str,
    timeout_seconds: int,
) -> dict[str, object]:
    deadline = time.time() + timeout_seconds
    last_detail: dict[str, object] | None = None
    while time.time() < deadline:
        detail = _get_json(f"{api_base_url}/api/v1/scans/{scan_id}")
        jobs = detail["enrichment_jobs"]
        last_detail = detail
        if jobs and all(job["status"] in {"completed", "failed"} for job in jobs):
            return detail
        time.sleep(2)
    raise RuntimeError(
        f"Timed out waiting for enrichment jobs to finish for scan {scan_id}. "
        f"Last response: {json.dumps(last_detail or {}, ensure_ascii=True)}"
    )


def _wait_for_health(url: str, timeout_seconds: int) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            payload = _get_json(url)
            if payload.get("status") == "ok":
                return
        except Exception:
            pass
        time.sleep(2)
    raise RuntimeError(f"Timed out waiting for API health at {url}.")


def _get_api_base_url(backend_dir: Path) -> str:
    env_path = backend_dir / ".env"
    host_port = os.getenv("BACKEND_HOST_PORT")
    if not host_port and env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == "BACKEND_HOST_PORT":
                host_port = value.strip()
                break
    if not host_port:
        host_port = "18000"
    return f"http://127.0.0.1:{host_port}"


def _get_json(url: str) -> dict[str, object] | list[dict[str, object]]:
    with request.urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_json(url: str, payload: dict[str, object]) -> dict[str, object]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Request to {url} failed with status {exc.code}: {response_body}"
        ) from exc


def _run(
    command: list[str],
    *,
    cwd: Path,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        message = "\n".join(
            [
                f"Command failed: {' '.join(command)}",
                result.stdout.strip(),
                result.stderr.strip(),
            ]
        ).strip()
        raise RuntimeError(message)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
