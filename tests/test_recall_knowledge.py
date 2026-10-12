"""Story 6: knowledge notes, catalog, ranking and the domain boundary in the recall."""

import subprocess
from datetime import datetime
from pathlib import Path

import pytest

from dory.config import Config
from dory.project import project_for_root
from dory.recall import recall
from dory.state import StateDir

NOW = datetime(2026, 10, 11, 12, 0)


def make_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    return path


def note(vault: Path, relative: str, **meta: str) -> Path:
    path = vault / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["---", *(f"{key}: {value}" for key, value in meta.items()), "---", "Text."]
    path.write_text("\n".join(lines) + "\n")
    return path


def knowledge(vault: Path, relative: str, projects: list[str], **meta: str) -> Path:
    links = ", ".join(f'"[[{name}]]"' for name in projects)
    defaults = {
        "type": "gotcha",
        "projects": f"[{links}]",
        "domain": "work",
        "summary": f"Summary {Path(relative).stem}",
        "when": f"When {Path(relative).stem}",
        "pinned": "false",
        "status": "active",
        "superseded_by": "",
        "created": "2026-10-01",
        "updated": "2026-10-01",
        "sources": '["[[s-1]]"]',
    }
    return note(vault, relative, **{**defaults, **meta})


def overview(vault: Path, name: str, domain: str = "work") -> None:
    note(vault, f"projects/{name}/{name}.md", type="project", domain=domain, summary=name)


@pytest.fixture
def world(tmp_path):
    vault = tmp_path / "vault"
    config = Config(vault=vault, state_dir=tmp_path / "state")
    projects_file = StateDir(config.state_dir).projects_file
    repos = {}
    for name in ("ai-assistant-hub", "ai-assistant-hub-infrastructure", "haushalt"):
        repos[name] = make_repo(tmp_path / "code" / name)
        project_for_root(repos[name].resolve(), projects_file)
    overview(vault, "ai-assistant-hub")
    overview(vault, "ai-assistant-hub-infrastructure")
    overview(vault, "haushalt", domain="private")
    note(vault, "notes/shopping-list.md", type="list", domain="private", summary="Shopping")
    note(vault, "notes/invoices.md", type="register", summary="Open invoices")
    home = tmp_path / "home"
    home.mkdir()
    return config, repos, home


def hook(cwd: Path) -> dict:
    return {
        "session_id": "new",
        "transcript_path": "/x/new.jsonl",
        "cwd": str(cwd),
        "source": "startup",
    }


def test_private_notes_never_reach_a_work_project_not_even_the_catalog(world):
    config, repos, _ = world
    vault = config.vault
    knowledge(vault, "projects/ai-assistant-hub/ai-assistant-hub-loki.md", ["ai-assistant-hub"])
    knowledge(
        vault,
        "projects/ai-assistant-hub/ai-assistant-hub-doctor.md",
        ["ai-assistant-hub"],
        domain="private",
        summary="Doctor appointment moved",
    )
    knowledge(vault, "general/taxes.md", [], domain="private", summary="Tax return due in March")
    knowledge(vault, "general/uv-instead-of-pip.md", [], summary="uv instead of pip")

    text = recall(hook(repos["ai-assistant-hub"]), config, now=NOW)

    assert "Summary ai-assistant-hub-loki" in text
    assert "uv instead of pip" in text
    for private in (
        "Doctor appointment",
        "ai-assistant-hub-doctor",
        "Tax return",
        "shopping-list",
        "invoices",
    ):
        assert private not in text


def test_note_shared_by_two_projects_shows_summary_when_and_path(world):
    config, repos, _ = world
    knowledge(
        config.vault,
        "projects/ai-assistant-hub/ai-assistant-hub-loki-uid-10001.md",
        ["ai-assistant-hub", "ai-assistant-hub-infrastructure"],
        summary="Loki only starts with UID 10001 on the volume.",
        when="When deploying Loki",
    )

    text = recall(hook(repos["ai-assistant-hub-infrastructure"]), config, now=NOW)

    assert "Loki only starts with UID 10001 on the volume." in text
    assert "When deploying Loki" in text
    assert "projects/ai-assistant-hub/ai-assistant-hub-loki-uid-10001.md" in text


def test_catalog_outside_a_repo_lists_shopping_list_and_invoices(world):
    config, _, home = world

    text = recall(hook(home), config, now=NOW)

    assert "## Catalog" in text
    assert "notes/shopping-list.md" in text
    assert "notes/invoices.md" in text
    assert "/dory:search" in text


def test_ranking_pinned_then_sources_then_updated_and_superseded_never(world):
    config, repos, _ = world
    vault = config.vault
    folder = "projects/ai-assistant-hub"
    project = ["ai-assistant-hub"]
    many = '["[[s-1]]", "[[s-2]]", "[[s-3]]"]'
    knowledge(vault, f"{folder}/a-pinned.md", project, pinned="true")
    knowledge(vault, f"{folder}/b-many.md", project, sources=many)
    knowledge(vault, f"{folder}/c-recent.md", project, updated="2026-10-10")
    knowledge(vault, f"{folder}/d-old.md", project, updated="2026-09-01")
    knowledge(
        vault,
        f"{folder}/e-replaced.md",
        project,
        pinned="true",
        status="superseded",
        superseded_by='"[[c-recent]]"',
    )
    for index in range(30):
        knowledge(vault, f"{folder}/z-filler-{index:02}.md", project, updated="2026-01-01")
    small = Config(vault=vault, state_dir=config.state_dir, recall_budget_tokens=250)

    text = recall(hook(repos["ai-assistant-hub"]), small, now=NOW)

    loaded = text.split("## Catalog")[0]
    order = ("a-pinned", "b-many", "c-recent", "d-old")
    positions = [loaded.index(f"Summary {stem}") for stem in order]
    assert positions == sorted(positions)
    assert loaded.find("Summary z-filler") in (-1, *range(positions[-1], len(loaded)))
    assert "Summary z-filler-29" not in loaded  # budget ran out before the lowest-ranked
    assert "e-replaced" not in text
    assert len(text) <= 250 * 4


def test_notes_that_did_not_fit_appear_in_the_catalog(world):
    config, repos, _ = world
    note(config.vault, "notes/customers.md", type="register", domain="work", summary="Customers")
    for index in range(40):
        knowledge(
            config.vault,
            f"projects/ai-assistant-hub/ai-assistant-hub-n{index:02}.md",
            ["ai-assistant-hub"],
            summary="Long summary " + "x" * 120,
        )

    text = recall(hook(repos["ai-assistant-hub"]), config, now=NOW)

    loaded, catalog = text.split("## Catalog")
    names = [f"ai-assistant-hub-n{index:02}" for index in range(40)]
    first_missing = next(name for name in names if f"{name}.md" not in loaded)
    assert names.index(first_missing) > 0
    assert f"{first_missing}: projects/ai-assistant-hub/{first_missing}.md" in catalog
    assert "customers: notes/customers.md" in catalog  # lists survive a full budget
    assert text.endswith("[... truncated, more with /dory:search ...]")
    assert len(text) <= config.recall_budget_tokens * 4


def test_private_project_loads_private_knowledge_and_lists(world):
    config, repos, _ = world
    knowledge(
        config.vault, "general/taxes.md", [], domain="private", summary="Tax return due in March"
    )

    text = recall(hook(repos["haushalt"]), config, now=NOW)

    assert "Tax return due in March" in text
    assert "notes/shopping-list.md" in text


def test_notes_of_other_projects_are_not_loaded(world):
    config, repos, _ = world
    knowledge(config.vault, "projects/teko/teko-x.md", ["teko"], summary="Only Teko")

    text = recall(hook(repos["ai-assistant-hub"]), config, now=NOW)

    assert "Only Teko" not in text


def test_no_heading_without_content(world):
    config, repos, home = world
    knowledge(config.vault, "general/uv-instead-of-pip.md", [], summary="uv instead of pip")

    for cwd in (repos["ai-assistant-hub"], home):
        lines = recall(hook(cwd), config, now=NOW).splitlines()
        for index, line in enumerate(lines):
            if line.startswith("## "):
                following = lines[index + 1] if index + 1 < len(lines) else ""
                assert following.strip(), f"empty section: {line}"
                assert not following.startswith("## "), f"empty section: {line}"
