from __future__ import annotations

import os
import time

from conftest import assistant, user, write_transcript
from transcript import (after_anchor, count_user_messages, cwd_of, find_transcript, is_interactive,
                        last_uuid, read_entries, redact, reduce)

TOOL_RESULT = {"type": "user", "uuid": "r1", "message": {"role": "user", "content": [
    {"type": "tool_result", "tool_use_id": "x", "content": "file body"}]}}
META = {"type": "user", "uuid": "m1", "isMeta": True, "message": {"role": "user", "content": "<local-command>"}}
SIDE = {"type": "user", "uuid": "s1", "isSidechain": True, "message": {"role": "user", "content": "subagent prompt"}}


def entries():
    return [
        user("u1", "lies das file ein"),
        assistant("a1", {"type": "thinking", "thinking": "secret thoughts"},
                  {"type": "tool_use", "name": "Bash", "input": {"command": "cat notes.md", "description": "Read"}}),
        TOOL_RESULT,
        META,
        SIDE,
        assistant("a2", {"type": "text", "text": "Das File beschreibt ein Plugin."}),
        user("u2", "gut, weiter"),
        {"type": "system", "uuid": "x1"},
    ]


def test_read_entries_skips_half_written_last_line(tmp_path):
    p = write_transcript(tmp_path / "t.jsonl", entries())
    with open(p, "a", encoding="utf-8") as f:
        f.write('{"type": "user", "uuid": "broken", "mess')
    got = read_entries(p)
    assert [e["uuid"] for e in got][-1] == "x1"


def test_anchor_and_last_uuid():
    es = entries()
    assert [e["uuid"] for e in after_anchor(es, "a2")] == ["u2", "x1"]
    assert after_anchor(es, None) == es
    assert after_anchor(es, "unknown") == es
    assert last_uuid(es) == "x1"


def test_count_user_messages_ignores_tool_results_meta_and_sidechains():
    assert count_user_messages(entries()) == 2


def test_is_interactive_and_cwd():
    assert is_interactive(entries()) is True
    assert is_interactive([{"type": "user", "entrypoint": "sdk-cli"}]) is False
    assert is_interactive([]) is True
    assert cwd_of(entries()) == "/w/proj"


def test_reduce_keeps_text_and_tool_lines_only():
    out = reduce(entries())
    assert "USER: lies das file ein" in out
    assert "[tool_use: Bash cat notes.md]" in out
    assert "ASSISTANT: Das File beschreibt ein Plugin." in out
    assert "secret thoughts" not in out
    assert "file body" not in out
    assert "<local-command>" not in out
    assert "subagent prompt" not in out


def test_reduce_truncates_middle():
    es = [user(f"u{i}", f"msg{i} " + "x" * 100) for i in range(100)]
    out = reduce(es, limit=1000)
    assert len(out) < 1100
    assert "msg0" in out and "msg99" in out
    assert "characters truncated" in out


def test_redact_known_secret_shapes():
    text = "\n".join([
        "key sk-ant-api03-abcdefghijklmnopqrstuvwxyz here",
        "ghp_abcdefghijklmnopqrstuvwxyz0123456789",
        "github_pat_11ABCDEFG0abcdefghijklmnopqrstuvwxyz",
        "AKIAABCDEFGHIJKLMNOP",
        "xoxb-1234567890-abcdefghij",
        "-----BEGIN RSA PRIVATE KEY-----\nMIIEow\n-----END RSA PRIVATE KEY-----",
        "API_KEY=supersecret",
        "  db_password: hunter2",
    ])
    out = redact(text)
    for leaked in ["abcdefghijklmnopqrstuvwxyz", "AKIAABCDEFGHIJKLMNOP", "MIIEow", "supersecret", "hunter2",
                   "1234567890-abcdefghij"]:
        assert leaked not in out
    assert out.count("[REDACTED]") == 8
    assert "API_KEY=[REDACTED]" in out


def test_redact_leaves_normal_text():
    text = "Das Token-Budget liegt bei 4000 Zeichen.\nWir nutzen sk als Abkürzung."
    assert redact(text) == text


def test_find_transcript_exact_then_newest(tmp_path):
    a = write_transcript(tmp_path / "p1" / "aaa.jsonl", [user("u", "x")])
    b = write_transcript(tmp_path / "p2" / "bbb.jsonl", [user("u", "x")])
    old = time.time() - 100
    os.utime(a, (old, old))
    assert find_transcript(tmp_path, "aaa") == a
    assert find_transcript(tmp_path, "missing") == b
    assert find_transcript(tmp_path, None) == b
    assert find_transcript(tmp_path / "none", "x") is None


def test_redact_inline_json_header_and_tool_forms():
    text = "\n".join([
        "export ANTHROPIC_API_KEY=abc123secret",
        '{"api_key": "def456secret"}',
        "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9secret",
        '[tool_use: Bash curl -H "X-Api-Token: ghi789secret"]',
        "sk_live_abcdefghijklmnop1234",
    ])
    out = redact(text)
    for leaked in ["abc123secret", "def456secret", "eyJhbGciOiJIUzI1NiJ9secret", "ghi789secret", "abcdefghijklmnop1234"]:
        assert leaked not in out


def test_reduce_redacts_before_truncating():
    key = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowSECRETBODY\n-----END RSA PRIVATE KEY-----"
    es = [user("u1", key), assistant("a1", {"type": "text", "text": "b" * 200})]
    assert "SECRETBODY" not in reduce(es, limit=120)


def test_redact_whole_multi_word_and_quoted_values():
    text = "\n".join([
        "password: correct horse battery staple",
        'DB_PASSWORD="my long pass phrase"',
        '{"password": "two words here"}',
        "token=abc,def123",
    ])
    out = redact(text)
    for leaked in ["horse", "battery", "long pass", "words here", "def123"]:
        assert leaked not in out


def test_redact_leaves_prose_and_code_keywords():
    text = "\n".join([
        "This covers the basic functionality and basic authentication.",
        "sorted(paths, key=lambda p: p.name)",
        "max_tokens=4096",
        "monkey: banana",
        "Keyword: dory",
    ])
    assert redact(text) == text


def test_count_user_messages_ignores_slash_commands_and_their_output():
    es = [
        user("c1", "<command-name>/clear</command-name>\n<command-message>clear</command-message>"),
        user("c2", "<command-message>dory:save</command-message>\n<command-name>/dory:save</command-name>"),
        user("c3", "<local-command-stdout></local-command-stdout>"),
        user("c4", "<local-command-caveat>The command below was run directly</local-command-caveat>"),
        user("u1", "echte Frage"),
    ]
    assert count_user_messages(es) == 1
