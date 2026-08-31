"""Rule coverage: canonical artifact shapes must match, ordinary prose must not.

The Claude samples mirror the shapes documented in
anthropics/claude-code#66504; other-agent samples cover the generic patterns.
"""

import pytest

from aisweep.config import build_allow_patterns, build_effective_rules
from aisweep.scanner import match_message

CASES = [
    # claude-session-url
    ("claude-session-url", "try https://claude.ai/code/session_abc123 later", True),
    ("claude-session-url", "transcript: https://claude.com/code/session_x", True),
    ("claude-session-url", "docs at https://docs.anthropic.com/en/docs", False),
    ("claude-session-url", "mirror at https://example.com/code/thing", False),
    # claude-generated-with
    (
        "claude-generated-with",
        "🤖 Generated with [Claude Code](https://claude.com/claude-code)",
        True,
    ),
    ("claude-generated-with", "generated with claude code", True),
    ("claude-generated-with", "Generated with Cursor", False),
    ("claude-generated-with", "blessed with claude code review", False),
    # claude-coauthored
    ("claude-coauthored", "Co-Authored-By: Claude <noreply@anthropic.com>", True),
    ("claude-coauthored", "Co-Authored-By: Alice <alice@example.com>", False),
    # ai-coauthored (generic agent names in trailers)
    ("ai-coauthored", "Co-Authored-By: Cursor <agent@cursor.sh>", True),
    ("ai-coauthored", "Co-Authored-By: Kimi <kimi@moonshot.cn>", True),
    ("ai-coauthored", "Co-Authored-By: Bob <bob@example.com>", False),
    # ai-generated-with
    (
        "ai-generated-with",
        "🤖 Generated with [GitHub Copilot](https://github.com/features/copilot)",
        True,
    ),
    ("ai-generated-with", "Generated with Aider v0.30", True),
    ("ai-generated-with", "Built with love", False),
]


@pytest.mark.parametrize(("rule_id", "line", "expected"), CASES)
def test_rule_matches(rule_id, line, expected):
    rules = build_effective_rules({})
    hits = match_message(line, rules)
    matched_ids = {r.id for r, *_ in hits}
    assert (rule_id in matched_ids) is expected, f"{rule_id}: {line!r}"


def test_dirty_message_lines_and_rules():
    message = (
        "feat: add user login\n"
        "\n"
        "Implements the login form and wires it to the API.\n"
        "\n"
        "🤖 Generated with [Claude Code](https://claude.com/claude-code)\n"
        "\n"
        "Co-Authored-By: Claude <noreply@anthropic.com>\n"
        "\n"
        "https://claude.ai/code/session_abc123def456\n"
    )
    hits = match_message(message, build_effective_rules({}))
    assert {(r.id, line_no) for r, line_no, _, _ in hits} == {
        ("claude-generated-with", 5),
        ("claude-coauthored", 7),
        ("claude-session-url", 9),
    }


def test_allow_patterns_suppress_findings():
    message = "Co-Authored-By: Claude <noreply@anthropic.com>\n"
    allow = build_allow_patterns({"allow_patterns": ["noreply@anthropic\\.com"]})
    hits = match_message(message, build_effective_rules({}), allow)
    assert hits == []


def test_find_reports_line_number_and_text():
    from aisweep.rules import DEFAULT_RULES

    rule = next(r for r in DEFAULT_RULES if r.id == "claude-session-url")
    text = "first\nsecond https://claude.ai/code/s1 third\nlast"
    (line_no, line, matched) = rule.find(text)[0]
    assert line_no == 2
    assert line == "second https://claude.ai/code/s1 third"
    assert matched == "https://claude.ai/code/s1"
