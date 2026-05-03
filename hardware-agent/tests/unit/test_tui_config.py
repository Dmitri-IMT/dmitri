"""Unit tests for agent.tui.config — OS defaults, load/save, validation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from agent.tui.config import (
    DmitriConfig,
    default_config_path,
    default_results_dir,
    load_config,
    resolve_display_path,
    save_config,
    validate_results_path,
)


class TestDefaultResultsDir:
    def test_not_downloads(self):
        result = default_results_dir()
        assert "Downloads" not in result
        assert "downloads" not in result

    @patch("agent.tui.config.platform.system", return_value="Windows")
    @patch.dict("os.environ", {"LOCALAPPDATA": "C:\\Users\\test\\AppData\\Local"})
    def test_windows(self, _mock_system):
        result = default_results_dir()
        assert result == "C:\\Users\\test\\AppData\\Local\\Dmitri\\results"

    @patch("agent.tui.config.platform.system", return_value="Linux")
    @patch.dict("os.environ", {"XDG_DATA_HOME": "/home/user/.local/share"}, clear=False)
    def test_linux_with_xdg(self, _mock_system):
        result = default_results_dir()
        assert result == str(Path("/home/user/.local/share/dmitri/results"))

    @patch("agent.tui.config.platform.system", return_value="Linux")
    @patch.dict("os.environ", {}, clear=False)
    def test_linux_without_xdg(self, _mock_system):
        # Falls back to ~/.local/share
        result = default_results_dir()
        assert "dmitri" in result
        assert "results" in result
        assert "Downloads" not in result

    @patch("agent.tui.config.platform.system", return_value="Darwin")
    @patch.dict("os.environ", {}, clear=False)
    def test_macos(self, _mock_system):
        result = default_results_dir()
        assert "dmitri" in result
        assert "results" in result


class TestDefaultConfigPath:
    @patch("agent.tui.config.platform.system", return_value="Windows")
    @patch.dict("os.environ", {"LOCALAPPDATA": "C:\\Users\\test\\AppData\\Local"})
    def test_windows(self, _mock_system):
        result = default_config_path()
        assert result == Path("C:\\Users\\test\\AppData\\Local\\Dmitri\\config.toml")

    @patch("agent.tui.config.platform.system", return_value="Linux")
    @patch.dict("os.environ", {"XDG_CONFIG_HOME": "/home/user/.config"}, clear=False)
    def test_linux_with_xdg(self, _mock_system):
        result = default_config_path()
        assert result == Path("/home/user/.config/dmitri/config.toml")


class TestLoadConfig:
    def test_returns_none_when_no_file(self, tmp_path):
        result = load_config(tmp_path / "nonexistent" / "config.toml")
        assert result is None

    def test_returns_none_when_file_has_no_results_dir(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text('something_else = "hi"\n', encoding="utf-8")
        result = load_config(config_file)
        assert result is None

    def test_loads_valid_config(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text('results_dir = "/home/user/scans"\n', encoding="utf-8")
        result = load_config(config_file)
        assert result is not None
        assert result.results_dir == "/home/user/scans"

    def test_loads_windows_path(self, tmp_path):
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            'results_dir = "C:\\\\Users\\\\test\\\\Dmitri\\\\results"\n',
            encoding="utf-8",
        )
        result = load_config(config_file)
        assert result is not None
        assert result.results_dir == "C:\\Users\\test\\Dmitri\\results"


class TestSaveConfig:
    def test_save_and_load_roundtrip(self, tmp_path):
        config_file = tmp_path / "dmitri" / "config.toml"
        original = DmitriConfig(results_dir="/home/user/my-scans")
        save_config(original, config_file)
        loaded = load_config(config_file)
        assert loaded is not None
        assert loaded.results_dir == original.results_dir

    def test_save_creates_parent_dirs(self, tmp_path):
        config_file = tmp_path / "deep" / "nested" / "config.toml"
        assert not config_file.parent.exists()
        save_config(DmitriConfig(results_dir="/tmp/results"), config_file)
        assert config_file.exists()

    def test_save_is_atomic_no_tmp_left(self, tmp_path):
        config_file = tmp_path / "config.toml"
        save_config(DmitriConfig(results_dir="/tmp/results"), config_file)
        tmp_file = config_file.with_suffix(".toml.tmp")
        assert not tmp_file.exists()
        assert config_file.exists()

    def test_save_windows_path_roundtrip(self, tmp_path):
        config_file = tmp_path / "config.toml"
        original = DmitriConfig(
            results_dir="C:\\Users\\test\\AppData\\Local\\Dmitri\\results"
        )
        save_config(original, config_file)
        loaded = load_config(config_file)
        assert loaded is not None
        assert loaded.results_dir == original.results_dir

    def test_save_overwrites_existing(self, tmp_path):
        config_file = tmp_path / "config.toml"
        save_config(DmitriConfig(results_dir="/first"), config_file)
        save_config(DmitriConfig(results_dir="/second"), config_file)
        loaded = load_config(config_file)
        assert loaded is not None
        assert loaded.results_dir == "/second"


class TestValidateResultsPath:
    def test_rejects_empty_path(self):
        assert validate_results_path("") is not None
        assert validate_results_path("   ") is not None

    def test_rejects_file_as_dir(self, tmp_path):
        file_path = tmp_path / "afile.txt"
        file_path.write_text("content")
        error = validate_results_path(str(file_path))
        assert error is not None
        assert "not a directory" in error

    def test_accepts_valid_new_path(self, tmp_path):
        new_dir = tmp_path / "new_results"
        error = validate_results_path(str(new_dir))
        assert error is None
        assert new_dir.is_dir()

    def test_accepts_existing_dir(self, tmp_path):
        existing_dir = tmp_path / "existing"
        existing_dir.mkdir()
        error = validate_results_path(str(existing_dir))
        assert error is None

    def test_creates_nested_dirs(self, tmp_path):
        nested = tmp_path / "a" / "b" / "c"
        error = validate_results_path(str(nested))
        assert error is None
        assert nested.is_dir()


class TestResolveDisplayPath:
    def test_empty_string(self):
        assert resolve_display_path("") == ""
        assert resolve_display_path("   ") == ""

    def test_expands_tilde(self):
        result = resolve_display_path("~/scans")
        assert "~" not in result
        assert "scans" in result

    def test_returns_absolute(self):
        result = resolve_display_path("relative/path")
        assert Path(result).is_absolute()
