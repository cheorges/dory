"""Record 003, Story S6: `dory search` finds single entries of the knowledge and notes files."""

import os
import subprocess
from pathlib import Path

import pytest

from dory import search as search_module
from dory.config import Config
from dory.project import project_for_root
from dory.search import search
from dory.state import StateDir

ROOT = Path(__file__).resolve().parents[1]
HUB = "projects/ai-assistant-hub"
HUB_KNOWLEDGE = """---
type: knowledge
domain: work
summary: KoliChat platform
---
## Pitfalls
- **Loki only starts if UID 10001 owns the data directory.** Run `chown -R 10001` before
  deploying.

## Facts
- **Grafana dashboards live in the repository under dashboards/.** Edit them there, not in the
  web interface.
"""


def write(vault: Path, relative: str, text: str) -> None:
    path = vault / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def note(vault: Path, relative: str, meta: dict[str, str], body: str = "Text.") -> None:
    lines = ["---", *(f"{key}: {value}" for key, value in meta.items()), "---", body]
    write(vault, relative, "\n".join(lines) + "\n")


def make_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    return path.resolve()


@pytest.fixture
def world(tmp_path):
    vault = tmp_path / "vault"
    config = Config(vault=vault, state_dir=tmp_path / "state")
    projects_file = StateDir(config.state_dir).projects_file
    hub = make_repo(tmp_path / "code" / "ai-assistant-hub")
    household = make_repo(tmp_path / "code" / "haushalt")
    for repo in (hub, household):
        project_for_root(repo, projects_file)
    write(vault, f"{HUB}/knowledge.md", HUB_KNOWLEDGE)
    write(vault, f"{HUB}/notes.md", "---\ntype: notes\n---\n- 2026-10-19: Loki port 3100 clashes\n")
    write(
        vault,
        "general/knowledge.md",
        "---\ntype: knowledge\ndomain: work\n---\n## How-to\n"
        "- **Deploy Python tools with uv instead of pip.** uv runs PEP 723 scripts.\n",
    )
    write(
        vault,
        "private/knowledge.md",
        "---\ntype: knowledge\ndomain: private\n---\n## Facts\n"
        "- **The home NAS deploys its backup at 02:00.** Synology Hyper Backup.\n",
    )
    write(
        vault,
        "projects/haushalt/knowledge.md",
        "---\ntype: knowledge\ndomain: private\n---\n## Facts\n"
        "- **The rent is deployed by standing order on the 25th.**\n",
    )
    home = tmp_path / "home"
    home.mkdir()
    return config, hub, household, home


def test_a_matching_entry_is_a_hit_with_its_file_and_its_neighbour_is_not(world):
    config, hub, _, _ = world

    text = search(config, hub, "loki")

    lines = text.splitlines()
    assert lines[0].startswith('Hits for "loki"')
    assert any(
        "Loki only starts if UID 10001 owns the data directory." in line
        and f"{HUB}/knowledge.md" in line
        and "Pitfalls" in line
        for line in lines
    ), text
    assert "Grafana" not in text


def test_a_lead_hit_comes_before_a_hit_in_the_text_only(world):
    config, hub, _, _ = world
    write(
        config.vault,
        "general/knowledge.md",
        "---\ntype: knowledge\ndomain: work\n---\n## Facts\n"
        "- **Promtail ships the container logs.** It pushes them to Loki.\n",
    )

    lines = search(config, hub, "loki").splitlines()[1:]

    lead = next(i for i, line in enumerate(lines) if "Loki only starts" in line)
    text_only = next(i for i, line in enumerate(lines) if "Promtail ships" in line)
    assert lead < text_only


def test_a_note_of_the_user_is_shown_whole(world):
    config, hub, _, _ = world
    long = (
        "Loki port 3100 clashes with Grafana on the customer VMs, so Loki runs on 3200 there "
        "and the dashboards point to the new port"
    )
    write(config.vault, f"{HUB}/notes.md", f"---\ntype: notes\n---\n- 2026-10-19: {long}\n")

    text = search(config, hub, "loki")

    assert f"- 2026-10-19: {long} → {HUB}/notes.md" in text


def test_a_list_saved_with_a_byte_order_mark_is_found(world):
    config, _, _, home = world
    path = config.vault / "notes" / "shopping.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\ntype: list\nsummary: Shopping\n---\n- [ ] Loki mug\n", "utf-8-sig")

    knowledge = config.vault / "general" / "knowledge.md"
    knowledge.write_text(
        "---\ntype: knowledge\ndomain: work\n---\n## Facts\n- **Loki.**\n", "utf-8-sig"
    )

    text = search(config, home, "loki knowledge")

    assert "notes/shopping.md" in text
    assert "type: knowledge" not in text


def test_in_a_work_project_nothing_private_is_shown(world):
    config, hub, _, _ = world

    text = search(config, hub, "deploy")

    assert "uv instead of pip" in text
    assert "Loki only starts" in text
    assert "NAS" not in text
    assert "rent" not in text
    assert "private/" not in text.split("\n", 1)[1]
    assert "haushalt" not in text


def test_outside_a_repository_and_in_a_private_project_both_domains_are_shown(world):
    config, _, household, home = world

    for cwd in (home, household):
        text = search(config, cwd, "deploy")
        assert "The home NAS deploys its backup at 02:00." in text
        assert "projects/haushalt/knowledge.md" in text
        assert "uv instead of pip" in text


def test_session_notes_and_lists_are_found_by_their_own_domain(world):
    config, hub, _, home = world
    vault = config.vault
    note(
        vault,
        "sessions/2026/10/2026-10-19-1200-ai-assistant-hub-abc-1.md",
        {"type": "session", "domain": "work", "summary": "Loki volume repaired on staging"},
    )
    note(
        vault,
        "sessions/2026/10/2026-10-19-1300-no-project-def-1.md",
        {"type": "session", "domain": "private", "summary": "Loki figurine ordered for the kids"},
    )
    note(vault, "notes/shopping-list.md", {"type": "list", "summary": "Shopping"}, "- [ ] Loki mug")
    note(
        vault,
        "notes/customers.md",
        {"type": "register", "domain": "work", "summary": "Customers"},
        "- Loki rollout at ASN",
    )

    work = search(config, hub, "loki")
    outside = search(config, home, "loki")

    assert "Loki volume repaired on staging" in work
    assert "notes/customers.md" in work
    assert "figurine" not in work
    assert "shopping-list" not in work
    assert "Loki figurine ordered for the kids" in outside
    assert "notes/shopping-list.md" in outside


def test_notes_and_overviews_of_an_earlier_version_are_not_shown(world):
    config, hub, _, home = world
    vault = config.vault
    note(vault, f"{HUB}/ai-assistant-hub.md", {"type": "project", "summary": "Loki overview"})
    note(
        vault,
        f"{HUB}/ai-assistant-hub-loki-uid-10001.md",
        {"type": "gotcha", "domain": "work", "summary": "Old Loki single note"},
    )
    note(vault, "general/loki-in-general.md", {"type": "fact", "summary": "Old Loki fact"})

    for cwd in (hub, home):
        text = search(config, cwd, "loki")
        assert "Old Loki" not in text
        assert "Loki overview" not in text
        assert "ai-assistant-hub.md" not in text


def test_no_hits_are_said_explicitly(world):
    config, hub, _, _ = world

    text = search(config, hub, "kubernetes helm")

    assert text.startswith('No hits for "kubernetes helm"')


def test_a_file_removed_during_the_search_is_skipped(world, monkeypatch):
    config, hub, _, _ = world
    real = search_module._read

    def vanishing(path: Path) -> str:
        if path.name == "notes.md":
            return ""
        return real(path)

    monkeypatch.setattr(search_module, "_read", vanishing)

    text = search(config, hub, "loki")

    assert "Loki only starts" in text
    assert "3100 clashes" not in text


def test_a_note_with_an_empty_or_list_type_does_not_break_the_search(world):
    config, hub, _, _ = world
    note(config.vault, "notes/empty-type.md", {"type": "", "domain": "work"})
    note(config.vault, "notes/list-type.md", {"type": "[list]"})
    note(config.vault, "sessions/2026/10/odd.md", {"type": "[session]", "summary": "Loki odd"})

    text = search(config, hub, "loki")

    assert "Loki only starts" in text


def test_cli_search_runs_in_the_current_directory(world):
    config, hub, _, _ = world
    env = {**os.environ, "DORY_VAULT": str(config.vault), "DORY_STATE_DIR": str(config.state_dir)}

    result = subprocess.run(
        [str(ROOT / "plugin" / "bin" / "dory"), "search", "loki", "deploy"],
        cwd=hub,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert f"{HUB}/knowledge.md" in result.stdout.splitlines()[1]
