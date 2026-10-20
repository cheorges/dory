"""Start the worker in the background, detached from the calling hook or command."""

import os
import subprocess
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def spawn_worker() -> None:
    if os.environ.get("DORY_NO_SPAWN") == "1":
        return
    subprocess.Popen(
        [str(PLUGIN_ROOT / "bin" / "dory"), "worker"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
