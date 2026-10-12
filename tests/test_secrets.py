import pytest

from dory.secrets import REDACTED, redact


@pytest.mark.parametrize(
    "text, leaked",
    [
        ("key sk-ant-api03-FAKEFAKEFAKEFAKEFAKE00", "FAKEFAKEFAKEFAKE"),
        ("token ghp_FAKEFAKEFAKEFAKEFAKEFAKE1234", "ghp_FAKE"),
        ("aws AKIAABCDEFGHIJKLMNOP here", "AKIAABCDEFGHIJKLMNOP"),
        ("-----BEGIN OPENSSH PRIVATE KEY-----\nabc\n-----END OPENSSH PRIVATE KEY-----", "abc"),
        ("password=hunter2hunter2", "hunter2"),
        ("API_TOKEN: abcdefghijklmnopqrstuvwxyz012345", "abcdefghijklmnop"),
        ("slack xoxb-1234567890-abcdefghij", "xoxb-1234567890"),
        ('{"password": "hunter2hunter2"}', "hunter2"),
        ('"client_secret": "abcdefghijklmnopqrstuv"', "abcdefghijklmnop"),
        ('curl -H "Authorization: Bearer abcdefghijklmnopqrstuvwxyz0123"', "abcdefghijklmnop"),
        ("stripe sk_live_ABCDEFGHIJKLMNOPQRST", "sk_live_ABCD"),
        ("gitlab glpat-ABCDEFGHIJKLMNOPQRSTUV", "glpat-ABCD"),
    ],
)
def test_known_secret_shapes_are_redacted(text, leaked):
    result = redact(text)

    assert leaked not in result
    assert REDACTED in result


def test_ordinary_text_is_left_alone():
    text = "Loki runs on port 3100, the token refresh happens every 5 minutes."

    assert redact(text) == text
