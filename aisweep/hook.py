"""commit-msg hook management.

The hook is the prevention half of aisweep: it runs ``aisweep check`` on every
commit message before the commit lands. Hooks are POSIX shell scripts; on
Windows they work inside Git Bash environments.
"""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

from .scanner import run_git

HOOK_NAME = "commit-msg"
MARKER_BEGIN = "# >>> aisweep-managed hook >>>"
MARKER_END = "# <<< aisweep-managed hook <<<"


class HookError(RuntimeError):
    """Raised when a hook cannot be installed or removed safely."""


def hooks_dir(repo: Path) -> Path:
    """Return the hooks directory, honouring ``core.hooksPath`` and worktrees."""
    out = run_git(repo, "rev-parse", "--git-path", "hooks").strip()
    path = Path(out)
    if not path.is_absolute():
        path = (Path(repo) / path).resolve()
    return path


def hook_path(repo: Path) -> Path:
    return hooks_dir(repo) / HOOK_NAME


def hook_script(python_exe: str, *, strict: bool = False) -> str:
    """Render the hook script that shells out to ``aisweep check``."""
    py = shlex.quote(python_exe)
    strict_flag = " --strict" if strict else ""
    return (
        "#!/bin/sh\n"
        f"{MARKER_BEGIN}\n"
        "# Installed by `aisweep hook install`. Remove with `aisweep hook uninstall`.\n"
        f"exec {py} -m aisweep check --msg-file \"$1\"{strict_flag}\n"
        f"{MARKER_END}\n"
    )


def status(repo: Path) -> str:
    """Return ``"installed"``, ``"missing"`` or ``"foreign"`` for the commit-msg hook."""
    path = hook_path(repo)
    if not path.exists():
        return "missing"
    if MARKER_BEGIN in path.read_text(encoding="utf-8", errors="replace"):
        return "installed"
    return "foreign"


def install(repo: Path, *, strict: bool = False, force: bool = False) -> Path:
    """Install (or refresh) the commit-msg hook; return the hook path.

    Refuses to clobber a hook aisweep did not install unless ``force`` is set;
    with ``force`` the previous hook is backed up next to the original.
    """
    directory = hooks_dir(repo)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / HOOK_NAME

    if path.exists():
        current = path.read_text(encoding="utf-8", errors="replace")
        if MARKER_BEGIN not in current:
            if not force:
                raise HookError(
                    f"{path} already exists and was not installed by aisweep; "
                    "use --force to back it up and replace it"
                )
            backup = path.with_name(HOOK_NAME + ".bak-aisweep")
            backup.write_text(current, encoding="utf-8")
        path.unlink()

    python_exe = os.environ.get("AISWEEP_PYTHON") or _current_python()
    path.write_text(hook_script(python_exe, strict=strict), encoding="utf-8")
    path.chmod(0o755)
    return path


def uninstall(repo: Path) -> bool:
    """Remove the hook if aisweep manages it. Returns ``True`` when removed."""
    path = hook_path(repo)
    if not path.exists():
        return False
    current = path.read_text(encoding="utf-8", errors="replace")
    if MARKER_BEGIN not in current:
        raise HookError(f"{path} was not installed by aisweep; remove it manually")
    path.unlink()
    return True


def _current_python() -> str:
    import sys

    return sys.executable or "python3"


def run_hook_probe(repo: Path, msg_file: Path) -> subprocess.CompletedProcess:
    """Execute the installed hook against ``msg_file`` (used by tests/docs)."""
    path = hook_path(repo)
    return subprocess.run(
        [str(path), str(msg_file)],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=60,
    )
