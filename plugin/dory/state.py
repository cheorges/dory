"""Layout of the state directory (queue, transcript copies, bundles, markers)."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StateDir:
    root: Path

    @property
    def queue(self) -> Path:
        return self.root / "queue"

    @property
    def transcripts(self) -> Path:
        return self.root / "transcripts"

    @property
    def work(self) -> Path:
        return self.root / "work"

    @property
    def baselines(self) -> Path:
        return self.root / "baselines"

    @property
    def done(self) -> Path:
        return self.root / "done"

    @property
    def failed(self) -> Path:
        return self.root / "failed"

    @property
    def sessions(self) -> Path:
        return self.root / "sessions"

    @property
    def summaries(self) -> Path:
        return self.root / "summaries"

    @property
    def lock_file(self) -> Path:
        return self.root / "worker.lock"

    @property
    def seen_file(self) -> Path:
        return self.root / "seen_uuids"

    @property
    def projects_file(self) -> Path:
        return self.root / "projects.json"

    def ensure(self) -> "StateDir":
        for directory in (
            self.queue,
            self.transcripts,
            self.work,
            self.baselines,
            self.done,
            self.failed,
            self.sessions,
            self.summaries,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        return self

    def load_seen(self) -> set[str]:
        if not self.seen_file.is_file():
            return set()
        return set(self.seen_file.read_text().split())

    def mark_seen(self, uuids: list[str]) -> None:
        if not uuids:
            return
        with self.seen_file.open("a") as handle:
            handle.write("\n".join(uuids) + "\n")
