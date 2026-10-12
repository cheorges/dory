"""Vault infrastructure shared by the worker and /dory:note: snapshots and the writing rules."""

import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from dory.config import Config
from dory.state import StateDir

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def snapshot(config: Config, state: StateDir) -> Path:
    config.vault.mkdir(parents=True, exist_ok=True)
    snapshots = state.root / "snapshots"
    snapshots.mkdir(parents=True, exist_ok=True)
    target = snapshots / datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    if subprocess.run(
        ["cp", "-cR", str(config.vault), str(target)], capture_output=True
    ).returncode:
        shutil.rmtree(target, ignore_errors=True)
        shutil.copytree(config.vault, target)
    for old in sorted(snapshots.iterdir())[: -config.snapshots_keep or None]:
        shutil.rmtree(old, ignore_errors=True)
    return target


def rules_text() -> str:
    skill = (PLUGIN_ROOT / "skills" / "rules" / "SKILL.md").read_text()
    return skill.split("---", 2)[2].lstrip() if skill.startswith("---") else skill
