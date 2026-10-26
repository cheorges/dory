"""How well link proposals find the files that should link a new library entry (Record 009).

The fixture vault `tests/fixtures/library-vault/` and the requests in
`tests/fixtures/library-requests.json` hold the expected links. This module measures the way
0.10.0's skill found them, as a baseline; `dory library-candidates` is measured against it.
"""

import importlib.util
import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import NamedTuple

import pytest

from dory.candidates import Draft, candidates
from dory.config import Config
from dory.library import CONTEXT_CHARS, library_context
from dory.project import Project, project_for_root
from dory.scopes import file_type, notes_folder_files, project_notes
from dory.state import StateDir

FIXTURES = Path(__file__).parent / "fixtures"
VAULT = FIXTURES / "library-vault"
REQUESTS = json.loads((FIXTURES / "library-requests.json").read_text(encoding="utf-8"))
TOP = 10


class Proposal(NamedTuple):
    """What a way of proposing gives for one request: files to link from, best first, and
    library entries that may be the same subject."""

    links: list[str]
    duplicates: list[str]


def old_way(vault: Path, request: dict) -> Proposal:
    """What 0.10.0's skill could find: the files `library-context` listed (the session project's
    notes, then the topic files) and the library entries that contain one of the request's key
    terms; a file whose title holds a term first, since the skill saw the titles."""
    project = request["project"]
    listed = project_notes(vault, Project(project, vault)) if project else []
    listed += [path for path in notes_folder_files(vault) if file_type(vault / path) == "topic"]
    entries = sorted(path.relative_to(vault) for path in (vault / "library").rglob("*.md"))
    terms = [term.casefold() for term in request["key_terms"]]

    def found(paths: list[Path]) -> list[str]:
        hits = [p for p in paths if any(t in (vault / p).read_text().casefold() for t in terms)]
        in_title = [p for p in hits if any(t in p.stem.casefold() for t in terms)]
        return [p.as_posix() for p in [*in_title, *(p for p in hits if p not in in_title)]]

    return Proposal(found(listed), found(entries))


def recall(proposed: dict[str, Proposal], top: int | None = TOP) -> float:
    """The share of all expected links among the first `top` proposals of their request."""
    expected = [(r["id"], link) for r in REQUESTS for link in r["expected_links"]]
    hits = sum(link in proposed[request].links[:top] for request, link in expected)
    return hits / len(expected)


def duplicates_found(proposed: dict[str, Proposal]) -> tuple[int, int]:
    """How many expected duplicates are among the proposed ones, and how many there are."""
    expected = [(r["id"], r["expected_duplicate"]) for r in REQUESTS if r["expected_duplicate"]]
    return sum(entry in proposed[request].duplicates for request, entry in expected), len(expected)


def leaks(proposed: dict[str, Proposal]) -> list[tuple[str, str]]:
    """Proposed files under a request's forbidden prefix, e.g. a private project's notes."""
    return [
        (r["id"], path)
        for r in REQUESTS
        if r["forbidden_prefix"]
        for path in [*proposed[r["id"]].links, *proposed[r["id"]].duplicates]
        if path.startswith(r["forbidden_prefix"])
    ]


def report(name: str, proposed: dict[str, Proposal]) -> str:
    found, total = duplicates_found(proposed)
    lines = [
        f"{name}: recall among the first {TOP} = {recall(proposed):.2f}, "
        f"without the cut = {recall(proposed, None):.2f}, duplicates {found} of {total}"
    ]
    for request in REQUESTS:
        missed = [
            link
            for link in request["expected_links"]
            if link not in proposed[request["id"]].links[:TOP]
        ]
        lines.append(f"  {request['id']}: missed {missed or 'nothing'}")
    return "\n".join(lines)


def test_every_expected_file_exists_and_every_request_is_complete():
    keys = {"id", "project", "title", "aliases", "content", "key_terms", "expected_links"}
    assert 8 <= len(REQUESTS) <= 10
    assert 140 <= len(list(VAULT.rglob("*.md"))) <= 170
    for request in REQUESTS:
        assert keys | {"expected_duplicate", "forbidden_prefix"} <= request.keys(), request["id"]
        assert len(request["key_terms"]) == 3, request["id"]
        for link in [*request["expected_links"], request["expected_duplicate"]]:
            assert link is None or (VAULT / link).is_file(), (request["id"], link)


def test_the_committed_vault_is_what_the_generator_writes(tmp_path):
    spec = importlib.util.spec_from_file_location("make_vault", FIXTURES / "make_library_vault.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    module.main(tmp_path / "vault")

    def tree(root: Path) -> dict[str, str]:
        return {p.relative_to(root).as_posix(): p.read_text() for p in root.rglob("*.md")}

    assert tree(tmp_path / "vault") == tree(VAULT)


def test_the_old_way_is_measured(capsys):
    proposed = {request["id"]: old_way(VAULT, request) for request in REQUESTS}

    with capsys.disabled():
        print("\n" + report("old way", proposed))
    assert 0 <= recall(proposed) <= 1


def new_way(vault: Path, request: dict) -> Proposal:
    """`dory library-candidates` on the request's draft."""
    project = Project(request["project"], vault) if request["project"] else None
    draft = Draft(request["title"], request["aliases"], request["content"])
    found, duplicates = candidates(vault, project, draft)
    return Proposal([c.path.as_posix() for c in found], [c.path.as_posix() for c in duplicates])


def test_the_candidates_beat_the_old_way_and_leak_nothing(capsys):
    old = {request["id"]: old_way(VAULT, request) for request in REQUESTS}
    started = time.perf_counter()
    new = {request["id"]: new_way(VAULT, request) for request in REQUESTS}
    seconds = (time.perf_counter() - started) / len(REQUESTS)

    with capsys.disabled():
        print("\n" + report("candidates", new) + f"\n  {seconds * 1000:.0f} ms per request")
    assert recall(new) >= 0.8 and recall(new) > recall(old)
    assert duplicates_found(new)[0] == duplicates_found(new)[1]
    assert leaks(new) == []
    assert seconds < 1


@pytest.fixture
def copied(tmp_path):
    vault = tmp_path / "vault"
    shutil.copytree(VAULT, vault)
    config = Config(vault=vault, state_dir=tmp_path / "state")
    repo = (tmp_path / "code" / "dory").resolve()
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    project_for_root(repo, StateDir(config.state_dir).projects_file)
    return config, repo


def test_the_library_context_of_the_fixture_stays_within_its_budget(copied):
    config, repo = copied

    text = library_context(config, repo)

    assert len(text) <= CONTEXT_CHARS, len(text)
    assert "projects/webshop/notes/Rechnungsstellung.md" in text
    assert "haushalt" not in text
