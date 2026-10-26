"""Replay real sessions into throwaway vaults with two versions of dory and compare (Record 008, S2).

    uv run python spike/replay.py --dry-run
    uv run python spike/replay.py --out <dir>            # both runs, then the comparison
    uv run python spike/replay.py --compare <dir>         # only the comparison of an earlier run

The sessions are the seven the vault review of 2026-10-23 looked at. Each run enqueues their
transcript copies from the real state directory, in their original order, into a fresh state
directory and a fresh vault, and drains the queue with that version's worker: `main` (exported
with `git archive`) against the working tree. The real vault and state are only read. The
repositories' current CLAUDE.md and records are captured, as the copies of the time are gone.

It works only until the first worker run of 0.11.0: that release deletes every transcript copy
whose entry is processed, these seven included, and `--dry-run` then shows `copy: False`. The
copies are not kept elsewhere on purpose, since they hold the unredacted sessions.
"""

import argparse
import json
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import replace
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STATE = Path.home() / ".local/state/dory-brain"
SESSIONS = [  # entry ids of the reviewed sessions, oldest first
    "20261022T185043.432311Z-a1091207-da23-4d11-9f69-569846cb429e",
    "20261022T185156.565992Z-a1091207-da23-4d11-9f69-569846cb429e",
    "20261022T200007.996461Z-8ec5bbd7-9214-40f9-bb4d-a190579cad0e",
    "20261023T064808.160105Z-0887febe-3b33-4002-9e85-f3fce756da55",
    "20261023T064820.814342Z-18dfa74b-f715-4eb3-9ae6-2b3122493771",
    "20261023T095023.675416Z-33134d49-0729-481c-9210-0b7e02c30986",
    "20261023T103528.901459Z-c19787fa-9e1c-4341-9527-432102710451",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--compare", type=Path)
    parser.add_argument("--model", help="worker model; default: the configured one")
    parser.add_argument("--code", type=Path, help=argparse.SUPPRESS)  # one run, in a subprocess
    args = parser.parse_args()
    if args.compare:
        print(compare(args.compare / "old" / "vault", args.compare / "new" / "vault"))
        return 0
    entries = [json.loads((STATE / "done" / f"{entry}.json").read_text()) for entry in SESSIONS]
    if args.dry_run:
        for entry_id, entry in zip(SESSIONS, entries, strict=True):
            copy = STATE / "transcripts" / f"{entry_id}.jsonl"
            print(f"{entry_id}  {entry['reason']:<18} {entry['cwd']}  copy: {copy.exists()}")
        return 0
    if args.code:
        return run_once(args.code, args.out, entries, args.model)
    out = args.out or Path(tempfile.mkdtemp(prefix="dory-replay-"))
    taken = [name for name in ("old", "new") if (out / name).exists()]
    if taken:  # a second run on top would mix into the first
        parser.error(f"{out} already holds a run ({', '.join(taken)}); choose another --out")
    old_code = out / "main-code"
    export_main(old_code)
    for name, code in (("old", old_code), ("new", REPO)):
        command = [sys.executable, __file__, "--code", str(code), "--out", str(out / name)]
        subprocess.run(command + (["--model", args.model] if args.model else []), check=True)
    print(compare(out / "old" / "vault", out / "new" / "vault"))
    return 0


def export_main(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    archive = subprocess.run(
        ["git", "-C", str(REPO), "archive", "main", "plugin"], capture_output=True, check=True
    ).stdout
    archive_path = target.with_suffix(".tar")
    archive_path.write_bytes(archive)
    with tarfile.open(archive_path) as tar:
        tar.extractall(target, filter="data")


def run_once(code: Path, out: Path, entries: list[dict], model: str | None) -> int:
    sys.path.insert(0, str(code / "plugin"))
    from dory import queue
    from dory.config import load_config
    from dory.ingest import make_process
    from dory.state import StateDir
    from dory.worker import run

    config = load_config()
    config = replace(
        config, vault=out / "vault", state_dir=out / "state", model=model or config.model
    )
    config.vault.mkdir(parents=True, exist_ok=True)
    state = StateDir(config.state_dir).ensure()
    for entry_id, entry in zip(SESSIONS, entries, strict=True):
        queue.enqueue(
            state,
            session_id=entry["session_id"],
            transcript=STATE / "transcripts" / f"{entry_id}.jsonl",
            cwd=entry["cwd"],
            reason=entry["reason"],
        )
    result = run(state, make_process(config, state))
    runs = [json.loads(line) for line in (state.root / "runs.log").read_text().splitlines()]
    cost = sum(item.get("cost_usd", 0) for item in runs)
    print(f"{code}: {result}, {len(runs)} runs, {cost:.2f} USD API equivalent", flush=True)
    return 0


def compare(old: Path, new: Path) -> str:
    sys.path.insert(0, str(REPO / "plugin"))
    from dory.entries import parse

    def leads(vault: Path) -> dict[str, list[str]]:
        files = sorted(vault.glob("projects/*/knowledge.md")) + sorted(vault.glob("notes/*.md"))
        return {
            str(path.relative_to(vault)): [
                f"{e.section}: {e.lead}" for e in parse(path.read_text())
            ]
            for path in files
        }

    before, after = leads(old), leads(new)
    lines = []
    for name in sorted(set(before) | set(after)):
        lines.append(f"\n## {name}")
        lines += [f"  old  {lead}" for lead in before.get(name, [])] or ["  old  (none)"]
        lines += [f"  new  {lead}" for lead in after.get(name, [])] or ["  new  (none)"]
    total = sum(map(len, before.values())), sum(map(len, after.values()))
    lines.append(f"\nEntries: old {total[0]}, new {total[1]}")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
