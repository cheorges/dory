from __future__ import annotations

import json
from pathlib import Path

import pytest


def write_note(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def write_transcript(path: Path, entries: list) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return path


def user(uuid: str, text: str, **extra) -> dict:
    return {"type": "user", "uuid": uuid, "entrypoint": "cli", "cwd": "/w/proj",
            "message": {"role": "user", "content": text}, **extra}


def assistant(uuid: str, *blocks: dict) -> dict:
    return {"type": "assistant", "uuid": uuid, "message": {"role": "assistant", "content": list(blocks)}}


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    v = tmp_path / "vault"
    v.mkdir()
    return v
