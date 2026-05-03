"""Persisted TUI configuration — load, save, validate, OS-aware defaults."""

from __future__ import annotations

import os
import platform
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class DmitriConfig:
    """User preferences persisted between sessions."""

    results_dir: str


def default_results_dir() -> str:
    """Return the OS-appropriate default results directory (absolute path)."""
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return str(Path(base) / "Dmitri" / "results")
    # Linux and macOS
    xdg_data = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return str(Path(xdg_data) / "dmitri" / "results")


def default_config_path() -> Path:
    """Return the OS-appropriate path for the config file."""
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return Path(base) / "Dmitri" / "config.toml"
    # Linux and macOS
    xdg_config = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(xdg_config) / "dmitri" / "config.toml"


def load_config(config_path: Path | None = None) -> DmitriConfig | None:
    """Load config from disk. Returns None if no config file exists (first run)."""
    path = config_path or default_config_path()
    if not path.is_file():
        return None
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    results_dir = data.get("results_dir")
    if not results_dir or not isinstance(results_dir, str):
        return None
    return DmitriConfig(results_dir=results_dir)


def save_config(config: DmitriConfig, config_path: Path | None = None) -> None:
    """Atomically persist config to disk (.tmp sibling + os.replace)."""
    path = config_path or default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".toml.tmp")
    content = _serialize_toml(config)
    tmp_path.write_text(content, encoding="utf-8")
    os.replace(tmp_path, path)


def validate_results_path(path_str: str) -> str | None:
    """Return error message if path is invalid, None if OK."""
    if not path_str or not path_str.strip():
        return "Path cannot be empty."
    try:
        resolved = Path(path_str.strip()).expanduser().resolve(strict=False)
    except (OSError, ValueError) as exc:
        return f"Invalid path: {exc}"
    if resolved.exists() and not resolved.is_dir():
        return f"Path exists but is not a directory: {resolved}"
    try:
        resolved.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        return f"Permission denied: cannot create {resolved}"
    except OSError as exc:
        return f"Cannot create directory: {exc}"
    return None


def resolve_display_path(path_str: str) -> str:
    """Resolve a path string for display (expand ~ and make absolute)."""
    if not path_str.strip():
        return ""
    try:
        return str(Path(path_str.strip()).expanduser().resolve(strict=False))
    except (OSError, ValueError):
        return path_str.strip()


def _serialize_toml(config: DmitriConfig) -> str:
    """Minimal TOML serialization for the config dataclass."""
    escaped = config.results_dir.replace("\\", "\\\\").replace('"', '\\"')
    return f'results_dir = "{escaped}"\n'
