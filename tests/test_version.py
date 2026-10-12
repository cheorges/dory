"""The version is declared in three places; they must agree."""

import json
import subprocess
import tomllib
from pathlib import Path

from dory import __version__

ROOT = Path(__file__).resolve().parents[1]


def test_package_plugin_and_project_versions_agree():
    plugin = json.loads((ROOT / "plugin" / ".claude-plugin" / "plugin.json").read_text())
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]

    assert plugin["version"] == project["version"] == __version__


def test_cli_prints_the_version():
    result = subprocess.run(
        [str(ROOT / "plugin" / "bin" / "dory"), "--version"], capture_output=True, text=True
    )

    assert result.stdout.strip() == f"dory {__version__}"
