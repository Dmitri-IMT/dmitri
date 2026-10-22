from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_release_workflow_keeps_signing_and_publication_permissions_separate():
    path = ROOT.parent / ".github/workflows/agent-release.yml"
    workflow = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    assert workflow["concurrency"] == {
        "group": "agent-apt-publication",
        "cancel-in-progress": "false",
    }
    assert workflow["permissions"] == {"contents": "read"}
    assert "agent-v*" in workflow["on"]["push"]["tags"]
    assert "schedule" in workflow["on"]

    jobs = workflow["jobs"]
    assert jobs["build"]["permissions"] == {"contents": "read"}
    assert jobs["sign"]["permissions"] == {"contents": "read"}
    assert jobs["sign"]["environment"]["name"] == "agent-release-signing"
    assert jobs["publish"]["permissions"] == {"contents": "write"}
    assert jobs["publish"]["environment"]["name"] == "agent-release-publishing"
    assert jobs["pages"]["permissions"] == {
        "pages": "write",
        "id-token": "write",
    }
    assert all(
        "AGENT_APT_SIGNING_SUBKEY" not in str(job)
        for name, job in jobs.items()
        if name != "sign"
    )
    for job in jobs.values():
        for step in job["steps"]:
            if "uses" in step:
                assert "@" in step["uses"]
                assert len(step["uses"].rsplit("@", 1)[1].split()[0]) == 40

    prepare_step = next(
        step for step in jobs["sign"]["steps"] if step.get("id") == "prepare"
    )
    prepare_script = prepare_step["run"]
    assert "publish-apt.sh verify-current" in prepare_script
    assert prepare_script.index("publish-apt.sh verify-current") < prepare_script.index(
        "publish-apt.sh prepare"
    )
    assert prepare_script.index("publish-apt.sh prepare") < prepare_script.index(
        "publish-apt.sh sign"
    )
    assert "--keyring backend/agent-release/public-keyring.gpg" in prepare_script


def test_ci_builds_and_installs_the_arm64_agent_and_installs_backend_test_extras():
    path = ROOT.parent / ".github/workflows/ci.yml"
    workflow = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    package_job = workflow["jobs"]["agent-package"]
    assert package_job["runs-on"] == "ubuntu-24.04-arm"
    package_steps = "\n".join(step.get("run", "") for step in package_job["steps"])
    package_content = "\n".join(
        f"{step.get('name', '')}\n{step.get('run', '')}"
        for step in package_job["steps"]
    )
    assert "hardware-agent-updater.deb" in package_steps
    assert 'Architecture)" = arm64' in package_steps
    assert 'Architecture)" = all' in package_steps
    assert "dpkg --install" in package_steps
    assert "/opt/dmitri-agent/.venv/bin/dmitri" in package_steps
    assert "Verify installed OPC UA runtime and health CLI" in package_content
    assert "import asyncua, cryptography" in package_steps
    assert (
        "Exercise inventory and bounded mapping against loopback OPC UA lab"
        in package_content
    )
    assert "hardware-agent/packaging/opcua-loopback-smoke.py" in package_steps
    smoke = (ROOT / "packaging/opcua-loopback-smoke.py").read_text(encoding="utf-8")
    assert '"127.0.0.1"' in smoke
    assert "opc.tcp://127.0.0.1:" in smoke

    backend_steps = "\n".join(
        step.get("run", "") for step in workflow["jobs"]["backend"]["steps"]
    )
    assert "uv sync --frozen --extra dev" in backend_steps
    assert "zero-skip backend suite" in backend_steps
