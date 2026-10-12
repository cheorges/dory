"""Spike (Story 1): build anonymised transcript fixtures for tests/fixtures/.

Two modes:
- synthetic: sessions created by the spike in a scratch repo. Content is ours and
  harmless; only machine-specific paths and account ids are replaced.
- skeleton: a real interactive transcript reduced to its structure. Every free-text
  string is replaced, only types, flags, ids, timestamps and tool names survive.

Usage:
    python3 spike/make_fixtures.py synthetic <src.jsonl> <dest.jsonl> <scratch_prefix>
    python3 spike/make_fixtures.py skeleton  <src.jsonl> <dest.jsonl>
"""

import json
import re
import sys
from pathlib import Path

HOME = str(Path.home())
ZERO_UUID = "00000000-0000-0000-0000-000000000000"
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
ACCOUNT_KEYS = {"ownerAccountUuid", "ownerOrganizationUuid", "organizationUuid", "bridgeSessionId"}
GIT_USER = re.compile(r"Git user: .*")
WRAPPER_TAG = re.compile(
    r"(</?(?:command-name|command-message|command-args|local-command-stdout|local-command-caveat|system-reminder)>)"
)

# Keys whose string values carry structure, not content.
KEEP_KEYS = {
    "type",
    "subtype",
    "uuid",
    "parentUuid",
    "leafUuid",
    "sessionId",
    "session_id",
    "timestamp",
    "role",
    "name",
    "id",
    "tool_use_id",
    "version",
    "userType",
    "entrypoint",
    "promptId",
    "requestId",
    "messageId",
    "model",
    "stop_reason",
    "permissionMode",
    "mode",
    "operation",
    "level",
    "gitBranch",
}


def scrub_paths(text: str, scratch_prefix: str | None) -> str:
    if scratch_prefix:
        text = text.replace(scratch_prefix, "/work")
        text = text.replace(scratch_prefix.replace("/", "-"), "-work")
    text = EMAIL.sub("user@example.com", text)
    text = GIT_USER.sub("Git user: user", text)
    text = text.replace(HOME, "/Users/USER")
    text = text.replace(HOME.replace("/", "-"), "-Users-USER")
    return text


def synthetic(obj, scratch_prefix):
    if isinstance(obj, dict):
        return {
            k: (
                ZERO_UUID
                if k in ACCOUNT_KEYS and isinstance(v, str)
                else synthetic(v, scratch_prefix)
            )
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [synthetic(v, scratch_prefix) for v in obj]
    if isinstance(obj, str):
        return scrub_paths(obj, scratch_prefix)
    return obj


def skeleton(obj, key=None):
    if isinstance(obj, dict):
        return {k: (ZERO_UUID if k in ACCOUNT_KEYS else skeleton(v, k)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [skeleton(v, key) for v in obj]
    if isinstance(obj, str):
        if key in KEEP_KEYS:
            return scrub_paths(obj, None)
        if key == "cwd":
            return "/Users/USER/project"
        # Keep every wrapper tag in place so condense filters see the real shape.
        parts = WRAPPER_TAG.split(obj)
        return "".join(
            p if WRAPPER_TAG.fullmatch(p) or not p.strip() else f"lorem ({len(p)} chars)"
            for p in parts
        )
    return obj


def main() -> None:
    mode, src, dest = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    scratch_prefix = sys.argv[4] if len(sys.argv) > 4 else None
    out = []
    for line in src.read_text(errors="replace").splitlines():
        if not line.strip():
            continue
        data = json.loads(line)
        data = synthetic(data, scratch_prefix) if mode == "synthetic" else skeleton(data)
        out.append(json.dumps(data, ensure_ascii=False))
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(out) + "\n")
    print(f"{dest}: {len(out)} lines")


if __name__ == "__main__":
    main()
