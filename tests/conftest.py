"""Shared fixtures: a throwaway git repository helper.

Global git config is detached (``GIT_CONFIG_GLOBAL``/``GIT_CONFIG_SYSTEM``
point at /dev/null) and identity is passed per command, so tests behave the
same on any machine.
"""

from __future__ import annotations

import os
import subprocess

import pytest

_ISOLATED_ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
}

_IDENTITY = [
    "-c", "user.name=Test User",
    "-c", "user.email=test@example.com",
    "-c", "commit.gpgsign=false",
]

# Shapes documented in anthropics/claude-code#66504.
DIRTY_MESSAGE = """feat: add user login

Implements the login form and wires it to the API.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>

https://claude.ai/code/session_abc123def456
"""

WARN_ONLY_MESSAGE = """feat: tweak parser

Co-Authored-By: Cursor <agent@cursor.sh>
"""

CLEAN_MESSAGE = "fix: handle empty payload in webhook parser"


class Repo:
    def __init__(self, path):
        self.path = path

    def git(self, *args: str, input: str | None = None) -> str:
        proc = subprocess.run(
            ["git", "-C", str(self.path), *_IDENTITY, *args],
            capture_output=True,
            text=True,
            input=input,
            env=_ISOLATED_ENV,
        )
        assert proc.returncode == 0, f"git {args} failed: {proc.stderr}"
        return proc.stdout

    def commit(self, message: str) -> str:
        self.git("commit", "-q", "--allow-empty", "-F", "-", input=message)
        return self.git("rev-parse", "HEAD").strip()


@pytest.fixture
def repo(tmp_path) -> Repo:
    r = Repo(tmp_path)
    r.git("init", "-q", "-b", "main")
    return r
