import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_agent_version.py"
_spec = importlib.util.spec_from_file_location("check_agent_version", _SCRIPT)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
parse_version = _module.parse_version
version_is_greater = _module.version_is_greater


def test_parse_version_requires_three_numbers():
    assert parse_version("1.0.0") == (1, 0, 0)


def test_parse_version_rejects_a_label():
    try:
        parse_version("1.0")
    except ValueError as exc:
        assert "MAJOR.MINOR.PATCH" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_greater_compares_each_position():
    assert version_is_greater("1.0.1", "1.0.0")
    assert version_is_greater("1.1.0", "1.0.9")
    assert version_is_greater("2.0.0", "1.9.9")
    assert not version_is_greater("1.0.0", "1.0.0")
    assert not version_is_greater("1.0.0", "1.0.1")
