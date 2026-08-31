"""Hook lifecycle and the real end-to-end commit gate."""

import os

import pytest

from aisweep.hook import (
    HookError,
    hooks_dir,
    install,
    run_hook_probe,
    status,
    uninstall,
)
from tests.conftest import CLEAN_MESSAGE, DIRTY_MESSAGE, WARN_ONLY_MESSAGE


def test_install_and_status(repo):
    path = install(repo.path)
    assert path.exists()
    assert os.access(path, os.X_OK)
    assert status(repo.path) == "installed"
    script = path.read_text()
    assert "aisweep check" in script
    assert script.startswith("#!/bin/sh")


def test_install_is_idempotent(repo):
    install(repo.path)
    install(repo.path)
    assert status(repo.path) == "installed"


def test_foreign_hook_is_protected(repo):
    hooks = hooks_dir(repo.path)
    hooks.mkdir(parents=True, exist_ok=True)
    custom = hooks / "commit-msg"
    custom.write_text("#!/bin/sh\necho custom\n")
    custom.chmod(0o755)

    with pytest.raises(HookError, match="not installed by aisweep"):
        install(repo.path)
    assert "custom" in custom.read_text()

    install(repo.path, force=True)
    assert status(repo.path) == "installed"
    backup = hooks / "commit-msg.bak-aisweep"
    assert backup.exists() and "custom" in backup.read_text()


def test_uninstall(repo):
    install(repo.path)
    assert uninstall(repo.path) is True
    assert status(repo.path) == "missing"
    assert uninstall(repo.path) is False


def test_uninstall_refuses_foreign_hook(repo):
    hooks = hooks_dir(repo.path)
    hooks.mkdir(parents=True, exist_ok=True)
    custom = hooks / "commit-msg"
    custom.write_text("#!/bin/sh\necho custom\n")
    with pytest.raises(HookError, match="remove it manually"):
        uninstall(repo.path)
    assert custom.exists()


def test_hook_blocks_dirty_commit_message(repo):
    install(repo.path)
    msg = repo.path / "commit-msg-file"
    msg.write_text(DIRTY_MESSAGE)
    proc = run_hook_probe(repo.path, msg)
    assert proc.returncode == 1
    assert "blocked" in proc.stdout
    assert "claude-session-url" in proc.stdout


def test_hook_allows_clean_message(repo):
    install(repo.path)
    msg = repo.path / "commit-msg-file"
    msg.write_text(CLEAN_MESSAGE)
    assert run_hook_probe(repo.path, msg).returncode == 0


def test_hook_warn_passes_non_strict_blocks_strict(repo):
    install(repo.path)
    msg = repo.path / "commit-msg-file"
    msg.write_text(WARN_ONLY_MESSAGE)
    assert run_hook_probe(repo.path, msg).returncode == 0

    install(repo.path, strict=True)
    assert run_hook_probe(repo.path, msg).returncode == 1


def test_hook_gate_rejects_dirty_commit_for_real(repo):
    """Full round trip: the installed hook rejects an actual `git commit`."""
    import subprocess

    from tests.conftest import _IDENTITY, _ISOLATED_ENV

    install(repo.path)
    proc = subprocess.run(
        ["git", "-C", str(repo.path), *_IDENTITY, "commit", "--allow-empty",
         "-m", "feat: x\n\nhttps://claude.ai/code/s1"],
        capture_output=True,
        text=True,
        env=_ISOLATED_ENV,
    )
    assert proc.returncode != 0
    assert "blocked" in proc.stdout + proc.stderr
