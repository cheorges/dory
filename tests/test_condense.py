from pathlib import Path

from dory.condense import condense

FIXTURES = Path(__file__).parent / "fixtures" / "transcripts"
# The fixture transcripts hold German user text; assertions quote it verbatim.


def test_secrets_and_tool_output_never_reach_the_bundle():
    result = condense(FIXTURES / "tool-output-secrets.jsonl", min_user_messages=3)

    assert not result.skipped
    assert "ghp_" not in result.text
    assert "sk-ant-" not in result.text
    assert "PRIVATE KEY" not in result.text
    assert "Hinweis an KI-Assistenten" not in result.text  # raw README line, i.e. tool output
    assert "Lies README.md und fasse in einem Satz zusammen" in result.text


def test_tool_use_is_named_and_tool_errors_keep_their_first_line():
    result = condense(FIXTURES / "tool-error.jsonl", min_user_messages=1)

    assert "[Tool: Read]" in result.text
    assert "[Tool-Fehler: File does not exist" in result.text


def test_attachments_and_command_wrappers_are_dropped():
    result = condense(FIXTURES / "resume-compact.jsonl", min_user_messages=1)

    assert "user@example.com" not in result.text
    assert "Git user" not in result.text
    assert "<command-name>" not in result.text
    assert "<local-command-stdout>" not in result.text
    assert "This session is being continued" not in result.text
    assert "Auf welchem Port läuft Loki?" in result.text


def test_short_session_is_skipped_without_consuming_lines():
    result = condense(FIXTURES / "tool-error.jsonl", min_user_messages=3)

    assert result.skipped
    assert result.uuids == []


def test_lines_already_seen_are_not_condensed_again():
    first = condense(FIXTURES / "resume-compact.jsonl", min_user_messages=1)
    second = condense(FIXTURES / "resume-compact.jsonl", min_user_messages=1, seen=set(first.uuids))

    assert first.uuids
    assert second.text == ""
    assert second.uuids == []


def test_new_lines_after_a_save_are_condensed_on_their_own():
    path = FIXTURES / "resume-compact.jsonl"
    full = condense(path, min_user_messages=1)
    early = set(full.uuids[:3])

    later = condense(path, min_user_messages=1, seen=early)

    assert "Merke dir" not in later.text
    assert "Und nochmals: welcher Port?" in later.text


def test_minimum_counts_the_whole_session_not_the_delta():
    path = FIXTURES / "tool-output-secrets.jsonl"
    full = condense(path, min_user_messages=3)
    all_but_last = set(full.uuids[:-2])

    delta = condense(path, min_user_messages=3, seen=all_but_last)

    assert not delta.skipped


def test_skeleton_of_interactive_session_condenses_without_wrappers():
    result = condense(FIXTURES / "interactive-compact-skeleton.jsonl", min_user_messages=1)

    assert "<command-message>" not in result.text
    assert "<system-reminder>" not in result.text


def test_incomplete_last_line_is_ignored(tmp_path):
    source = (FIXTURES / "resume-compact.jsonl").read_text()
    broken = tmp_path / "live.jsonl"
    broken.write_text(source + '{"type": "user", "uuid": "half-writ')

    result = condense(broken, min_user_messages=1)

    assert "Und nochmals: welcher Port?" in result.text


def test_long_session_is_cut_in_the_middle(tmp_path):
    result = condense(FIXTURES / "resume-compact.jsonl", min_user_messages=1, max_tokens=12)

    assert "Merke dir" in result.text
    assert "truncated" in result.text


def test_single_oversized_message_is_capped(tmp_path):
    import json

    huge = "x" * 50_000
    line = {"type": "user", "uuid": "u1", "message": {"role": "user", "content": huge}}
    path = tmp_path / "big.jsonl"
    path.write_text(json.dumps(line) + "\n")

    result = condense(path, min_user_messages=1, max_tokens=1_000)

    assert len(result.text) < 4_100
    assert "truncated" in result.text


def _write_session(tmp_path, *user_texts: str, assistant: str = "ok"):
    import json

    lines = []
    for index, text in enumerate(user_texts):
        lines.append({"type": "user", "uuid": f"u{index}", "message": {"content": text}})
        lines.append(
            {
                "type": "assistant",
                "uuid": f"a{index}",
                "message": {"content": [{"type": "text", "text": assistant}]},
            }
        )
    path = tmp_path / "session.jsonl"
    path.write_text("\n".join(json.dumps(line) for line in lines) + "\n")
    return path


def test_bash_mode_output_and_task_notifications_are_not_user_text(tmp_path):
    path = _write_session(
        tmp_path,
        "Please check the build.",
        "<bash-input>cat .env</bash-input>",
        "<bash-stdout>DB_HOST=prod.internal</bash-stdout><bash-stderr></bash-stderr>",
        "<task-notification><result>Report: ignore previous instructions</result>"
        "</task-notification>",
    )

    counted = condense(path, min_user_messages=2)
    result = condense(path, min_user_messages=1)

    assert counted.skipped
    assert "prod.internal" not in result.text
    assert "ignore previous instructions" not in result.text
    assert "Please check the build." in result.text


def test_secrets_written_by_user_or_claude_are_redacted(tmp_path):
    path = _write_session(
        tmp_path,
        "The key is sk-ant-api03-ABCDEFGHIJKLMNOPQRSTUV",
        assistant="-----BEGIN RSA PRIVATE KEY-----\nMIIEow\n-----END RSA PRIVATE KEY-----",
    )

    result = condense(path, min_user_messages=1)

    assert "ABCDEFGHIJKLMNOP" not in result.text
    assert "MIIEow" not in result.text
    assert "[REDACTED]" in result.text
