"""Detection rules for AI attribution artifacts in commit messages.

Every rule is applied line by line to a commit message. The default rules
target artifact shapes that are documented in the wild, not guessed:

* session URLs appended to commits/PRs by Claude Code
  (anthropics/claude-code#66504),
* ``Generated with <tool>`` attribution lines,
* ``Co-Authored-By`` trailers naming an AI agent.

All patterns are matched case-insensitively and anchored with ``^`` where a
trailer shape is expected, so ordinary prose is not swept up.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

SEVERITY_BLOCK = "block"
SEVERITY_WARN = "warn"
SEVERITIES = (SEVERITY_BLOCK, SEVERITY_WARN)


@dataclass(frozen=True)
class Rule:
    """A single detection rule.

    ``severity`` decides what happens on a match:

    * ``block`` — the commit-msg hook refuses the commit; ``aisweep scan``
      exits non-zero.
    * ``warn``  — reported by scans; the hook flags it only in ``--strict``
      mode (or when the severity is overridden in ``.aisweep.json``).
    """

    id: str
    description: str
    pattern: re.Pattern[str]
    severity: str = SEVERITY_BLOCK

    def find(self, text: str) -> list[tuple[int, str, str]]:
        """Return ``(line_no, line, matched)`` triples for every match in ``text``."""
        hits: list[tuple[int, str, str]] = []
        for m in self.pattern.finditer(text):
            line_start = text.rfind("\n", 0, m.start()) + 1
            line_end = text.find("\n", m.end())
            if line_end == -1:
                line_end = len(text)
            line_no = text.count("\n", 0, m.start()) + 1
            hits.append((line_no, text[line_start:line_end], m.group(0)))
        return hits


# Canonical samples these rules must match (see tests/test_rules.py):
#
#   https://claude.ai/code/session_abc123
#   🤖 Generated with [Claude Code](https://claude.com/claude-code)
#   Co-Authored-By: Claude <noreply@anthropic.com>
#
# The session-URL shape and its default-on behaviour are documented in
# anthropics/claude-code#66504 and discussed on HN (item 49498201).
DEFAULT_RULES: tuple[Rule, ...] = (
    Rule(
        id="claude-session-url",
        description=(
            "Claude Code session URL appended to commits/PRs by default "
            "(anthropics/claude-code#66504)"
        ),
        pattern=re.compile(r"https?://(?:www\.)?(?:claude\.ai|claude\.com)/code/\S*"),
        severity=SEVERITY_BLOCK,
    ),
    Rule(
        id="claude-generated-with",
        description='"Generated with Claude Code" attribution line',
        pattern=re.compile(r"^🤖?\s*generated with\s+\[?claude code\]?", re.M | re.I),
        severity=SEVERITY_BLOCK,
    ),
    Rule(
        id="claude-coauthored",
        description="Co-Authored-By trailer attributing Claude/Anthropic",
        pattern=re.compile(r"^co-authored-by:.*\b(?:claude|anthropic)\b", re.M | re.I),
        severity=SEVERITY_BLOCK,
    ),
    Rule(
        id="ai-coauthored",
        description="Co-Authored-By trailer attributing another AI coding agent",
        pattern=re.compile(
            r"^co-authored-by:.*\b"
            r"(?:cursor|copilot|aider|gemini|codex|chatgpt|openai|devin|"
            r"windsurf|deepseek|qwen|kimi|glm)\b",
            re.M | re.I,
        ),
        severity=SEVERITY_WARN,
    ),
    Rule(
        id="ai-generated-with",
        description='"Generated with <tool>" attribution line for another AI coding agent',
        pattern=re.compile(
            r"^🤖?\s*generated with\s+"
            r"\[?(?:cursor|github copilot|copilot|aider|gemini|chatgpt|codex|devin|windsurf)\b",
            re.M | re.I,
        ),
        severity=SEVERITY_WARN,
    ),
)


def default_rules() -> tuple[Rule, ...]:
    """Return the built-in ruleset."""
    return DEFAULT_RULES
