"""Spike (Story 1): end an interactive Claude Code session the way a person would.

Starts `claude` in a pseudo-terminal with the spike plugin, optionally sends $SPIKE_PROMPT,
then ends the session in one of two ways:
- tab-close: closes the terminal side of the pty (what closing a Terminal tab does,
  the kernel sends SIGHUP to the foreground process group)
- ctrl-c: presses Ctrl+C until claude exits (at most 5 times)

Send no prompt inside a repo: the global CLAUDE.md starts session-start workflows.

The spike plugin's hooks write into $DORY_SPIKE_LOG; this script only drives the session.

Usage:
    DORY_SPIKE_LOG=<dir> [SPIKE_PROMPT=...] python3 spike/interactive_exit_test.py tab-close|ctrl-c <cwd> <plugin_dir>
"""

import os
import pty
import select
import sys
import time


def drain(fd: int, seconds: float) -> bytes:
    out = b""
    end = time.time() + seconds
    while time.time() < end:
        ready, _, _ = select.select([fd], [], [], 0.2)
        if ready:
            try:
                chunk = os.read(fd, 65536)
            except OSError:
                break
            if not chunk:
                break
            out += chunk
    return out


def main() -> None:
    mode, cwd, plugin_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE")}
    env["TERM"] = "xterm-256color"
    pid, fd = pty.fork()
    if pid == 0:
        os.chdir(cwd)
        os.execvpe("claude", ["claude", "--plugin-dir", plugin_dir, "--model", "haiku"], env)

    drain(fd, 8)  # startup screen
    if os.environ.get("SPIKE_PROMPT"):
        os.write(fd, os.environ["SPIKE_PROMPT"].encode())
        time.sleep(0.5)
        os.write(fd, b"\r")
        drain(fd, 20)  # wait for the answer
    started = time.time()
    if mode == "tab-close":
        os.close(fd)
    else:
        # Ctrl+C until claude exits; the first press may only cancel running work.
        screen = b""
        for _ in range(5):
            os.write(fd, b"\x03")
            screen += drain(fd, 0.6)
            done, status = os.waitpid(pid, os.WNOHANG)
            if done:
                break
        with open(os.path.join(os.environ["DORY_SPIKE_LOG"], "ctrl-c-screen.txt"), "wb") as f:
            f.write(screen)
        if done:
            print(f"{mode}: claude exited after {time.time() - started:.1f}s, status={status}")
            return
    for _ in range(30):
        try:
            done, status = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            print(f"{mode}: claude exited after {time.time() - started:.1f}s")
            return
        if done:
            print(f"{mode}: claude exited after {time.time() - started:.1f}s, status={status}")
            return
        time.sleep(0.5)
    os.kill(pid, 9)
    print(f"{mode}: claude did not exit within 15s, killed")


if __name__ == "__main__":
    main()
