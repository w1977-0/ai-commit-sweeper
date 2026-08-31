"""Git history scanning.

aisweep reads commit messages with ``git log`` and matches every line against
the effective ruleset. It never touches the repository — no history rewriting,
no working-tree changes, no staged content inspection.
"""

from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .config import build_allow_patterns, build_effective_rules
from .rules import Rule

FIELD_SEP = "\x1f"
RECORD_SEP = "\x1e"
LOG_FORMAT = f"%H{FIELD_SEP}%h{FIELD_SEP}%an{FIELD_SEP}%aI{FIELD_SEP}%B{RECORD_SEP}"

# Long excerpts are noise in reports; keep the shape, drop the tail.
MAX_EXCERPT = 120


class GitError(RuntimeError):
    """Raised when a git invocation fails or the target is not a repository."""


@dataclass(frozen=True)
class Finding:
    """One artifact occurrence in one commit message."""

    commit: str
    short: str
    author: str
    date: str
    rule_id: str
    severity: str
    line_no: int
    line: str
    matched: str

    def excerpt(self, limit: int = 72) -> str:
        line = self.line.replace("\t", " ")
        if len(line) > limit:
            return line[: limit - 1] + "…"
        return line


@dataclass(frozen=True)
class CommitInfo:
    commit: str
    short: str
    author: str
    date: str
    message: str


@dataclass(frozen=True)
class ScanResult:
    repository: str
    range: str
    commits_scanned: int
    findings: list[Finding] = field(default_factory=list)

    @property
    def commits_with_findings(self) -> int:
        return len({f.commit for f in self.findings})

    def to_dict(self) -> dict:
        data = asdict(self)
        return data


def run_git(repo: Path, *args: str) -> str:
    """Run ``git -C <repo> <args>`` and return stdout; raise :class:`GitError`."""
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip().splitlines()
        raise GitError(detail[0] if detail else f"git {' '.join(args)} failed")
    return proc.stdout


def is_git_repo(path: Path) -> bool:
    try:
        run_git(path, "rev-parse", "--git-dir")
    except GitError:
        return False
    return True


def head_commit(repo: Path) -> str | None:
    """Return the resolved HEAD revision, or ``None`` on an unborn branch."""
    proc = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "-q", "HEAD"],
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip() or None if proc.returncode == 0 else None


def current_ref(repo: Path, rev: str | None, all_branches: bool) -> str:
    """Human-readable description of what will be scanned."""
    if all_branches:
        return "--all"
    if rev:
        return rev
    branch = run_git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()
    return branch if branch != "HEAD" else "detached HEAD"


def iter_commits(
    repo: Path,
    *,
    rev: str | None = None,
    all_branches: bool = False,
    since: str | None = None,
    max_count: int | None = None,
) -> list[CommitInfo]:
    """List commits in the requested range, oldest-log-order reversed (git order)."""
    args = ["log", f"--format={LOG_FORMAT}"]
    args.append("--all" if all_branches else (rev or "HEAD"))
    if since:
        args.append(f"--since={since}")
    if max_count is not None:
        args.append(f"--max-count={max_count}")
    out = run_git(repo, *args)
    commits: list[CommitInfo] = []
    for record in out.split(RECORD_SEP):
        if not record.strip():
            continue
        try:
            sha, short, author, date, message = record.strip("\n").split(FIELD_SEP, 4)
        except ValueError as exc:
            raise GitError(f"could not parse git log output: {exc}") from exc
        commits.append(
            CommitInfo(
                commit=sha,
                short=short,
                author=author,
                date=date[:10],
                message=message.rstrip("\n"),
            )
        )
    return commits


def match_message(
    text: str,
    rules: tuple[Rule, ...],
    allow_patterns: tuple = (),
) -> list[tuple[Rule, int, str, str]]:
    """Return ``(rule, line_no, line, matched)`` for every hit in ``text``."""
    hits: list[tuple[Rule, int, str, str]] = []
    for rule in rules:
        for line_no, line, matched in rule.find(text):
            if any(p.search(line) for p in allow_patterns):
                continue
            hits.append((rule, line_no, line, matched))
    return hits


def scan(
    repo: Path,
    config: dict | None = None,
    *,
    rev: str | None = None,
    all_branches: bool = False,
    since: str | None = None,
    max_count: int | None = None,
) -> ScanResult:
    """Scan the repository history and return a :class:`ScanResult`."""
    if not is_git_repo(repo):
        raise GitError(f"not a git repository: {repo}")

    if all_branches:
        has_commits = run_git(repo, "rev-list", "--all", "-n1").strip() != ""
        empty_ok = True
    else:
        has_commits = head_commit(repo) is not None
        empty_ok = rev is None or rev == "HEAD"

    if not has_commits and empty_ok:
        label = "--all" if all_branches else "HEAD (unborn)"
        return ScanResult(
            repository=str(repo.resolve()),
            range=label,
            commits_scanned=0,
            findings=[],
        )

    rules = build_effective_rules(config)
    allow = build_allow_patterns(config)

    findings: list[Finding] = []
    commits = iter_commits(
        repo, rev=rev, all_branches=all_branches, since=since, max_count=max_count
    )
    for commit in commits:
        for rule, line_no, line, matched in match_message(commit.message, rules, allow):
            findings.append(
                Finding(
                    commit=commit.commit,
                    short=commit.short,
                    author=commit.author,
                    date=commit.date,
                    rule_id=rule.id,
                    severity=rule.severity,
                    line_no=line_no,
                    line=line[:MAX_EXCERPT],
                    matched=matched[:MAX_EXCERPT],
                )
            )
    return ScanResult(
        repository=str(repo.resolve()),
        range=current_ref(repo, rev, all_branches),
        commits_scanned=len(commits),
        findings=findings,
    )
