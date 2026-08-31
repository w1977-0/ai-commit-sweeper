"""Command line interface.

Exit codes (stable, script/CI friendly):

* ``0`` — success, no findings (or hook allowed the message)
* ``1`` — findings reported (``scan``) or commit blocked (``check``)
* ``2`` — usage, configuration or hook errors
* ``3`` — target path is not a git repository
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .config import CONFIG_FILENAME, ConfigError, load_config
from .hook import HookError, hook_path
from .hook import install as hook_install
from .hook import status as hook_status
from .hook import uninstall as hook_uninstall
from .report import render_json, render_markdown
from .scanner import GitError, match_message, scan

SEVERITY_MARK = {"block": "✖", "warn": "⚠"}


def _repo_path(args: argparse.Namespace) -> Path:
    target = getattr(args, "path", None) or getattr(args, "repo", None)
    return Path(target).resolve() if target else Path.cwd().resolve()


def _load(args: argparse.Namespace, repo: Path) -> dict:
    explicit = Path(args.config).resolve() if getattr(args, "config", None) else None
    return load_config(repo, explicit)


# --------------------------------------------------------------------------- scan


def cmd_scan(args: argparse.Namespace) -> int:
    repo = _repo_path(args)
    config = _load(args, repo)
    result = scan(
        repo,
        config,
        rev=getattr(args, "rev", None),
        all_branches=args.all,
        since=getattr(args, "since", None),
        max_count=args.max,
    )
    if args.json:
        print(render_json(result))
    else:
        _print_human(result)
        if args.output:
            Path(args.output).write_text(render_markdown(result), encoding="utf-8")
            print(f"markdown report written to {args.output}")
    return 1 if result.findings else 0


def _print_human(result) -> None:
    repo_label = result.repository
    print(f"aisweep {__version__} — scanning {result.range} in {repo_label}")
    if result.commits_scanned == 0:
        print("no commits found — nothing to scan")
        return
    for f in result.findings:
        mark = SEVERITY_MARK.get(f.severity, "?")
        print(
            f"  {f.short} {f.date} {mark} {f.severity:<5} {f.rule_id:<22} {f.excerpt()}"
        )
    print(
        f"{result.commits_with_findings}/{result.commits_scanned} commit(s) contain "
        f"AI attribution artifacts ({len(result.findings)} finding(s))."
    )
    if result.findings:
        print("Prevent future artifacts in this repo: aisweep hook install")


# --------------------------------------------------------------------------- check


def cmd_check(args: argparse.Namespace) -> int:
    repo = _repo_path(args)
    config = _load(args, repo)
    from .config import build_allow_patterns, build_effective_rules

    try:
        text = Path(args.msg_file).read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise ConfigError(f"cannot read commit message file {args.msg_file}: {exc}") from exc

    rules = build_effective_rules(config)
    allow = build_allow_patterns(config)
    hits = match_message(text, rules, allow)

    blocking = [
        (rule, line_no, line, matched)
        for rule, line_no, line, matched in hits
        if rule.severity == "block" or args.strict
    ]
    warnings = [h for h in hits if h not in blocking]

    if not hits:
        return 0

    print("aisweep: commit message contains AI attribution artifacts:")
    for rule, _line_no, line, _matched in hits:
        mark = SEVERITY_MARK.get(rule.severity, "?")
        print(f"  {mark} {rule.severity:<5} {rule.id:<22} {line[:72]}")
    if not blocking and warnings:
        print("(warn-level only; commit allowed — tune severities in .aisweep.json)")
        return 0
    print(
        "commit blocked. Edit the message (drop the artifacts or configure "
        f"{CONFIG_FILENAME}), then commit again."
    )
    return 1


# --------------------------------------------------------------------------- report


def cmd_report(args: argparse.Namespace) -> int:
    repo = _repo_path(args)
    config = _load(args, repo)
    result = scan(
        repo,
        config,
        rev=getattr(args, "rev", None),
        all_branches=args.all,
        since=getattr(args, "since", None),
        max_count=args.max,
    )
    output = Path(args.output)
    output.write_text(render_markdown(result), encoding="utf-8")
    print(
        f"report: {len(result.findings)} finding(s) across "
        f"{result.commits_scanned} commit(s) -> {output}"
    )
    if args.json_output:
        Path(args.json_output).write_text(render_json(result), encoding="utf-8")
        print(f"json report written to {args.json_output}")
    return 1 if result.findings else 0


# --------------------------------------------------------------------------- hook


def cmd_hook(args: argparse.Namespace) -> int:
    repo = _repo_path(args)
    if args.hook_cmd == "install":
        path = hook_install(repo, strict=args.strict, force=args.force)
        mode = "strict" if args.strict else "default (block-level rules only)"
        print(f"commit-msg hook installed at {path} ({mode})")
        return 0
    if args.hook_cmd == "uninstall":
        removed = hook_uninstall(repo)
        print("commit-msg hook removed" if removed else "no aisweep hook found")
        return 0
    state = hook_status(repo)
    if state == "installed":
        print(f"commit-msg hook: installed ({hook_path(repo)})")
    elif state == "foreign":
        print(f"commit-msg hook: foreign hook at {hook_path(repo)} (not installed by aisweep)")
    else:
        print("commit-msg hook: not installed")
    return 0


# --------------------------------------------------------------------------- init


INIT_TEMPLATE = """{
  "disable": [],
  "severities": {},
  "allow_patterns": [],
  "extra_rules": []
}
"""


def cmd_init(args: argparse.Namespace) -> int:
    repo = _repo_path(args)
    target = repo / CONFIG_FILENAME
    if target.exists() and not args.force:
        print(f"{target} already exists (use --force to overwrite)")
        return 2
    target.write_text(INIT_TEMPLATE, encoding="utf-8")
    print(f"wrote {target}")
    return 0


# --------------------------------------------------------------------------- parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aisweep",
        description="Find and prevent AI-agent attribution artifacts in git commits.",
    )
    parser.add_argument("--version", action="version", version=f"aisweep {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser, scan_args: bool = True) -> None:
        p.add_argument("path", nargs="?", default=None, help="repository path (default: cwd)")
        p.add_argument("--repo", dest="repo", default=None, help="same as the positional path")
        p.add_argument("--config", default=None, help=f"path to {CONFIG_FILENAME}")
        if scan_args:
            p.add_argument("--all", action="store_true", help="scan all refs, not just HEAD")
            p.add_argument("--rev", default=None, help="revision or range to scan")
            p.add_argument("--since", default=None, help='e.g. "2026-01-01" or "2 weeks ago"')
            p.add_argument("--max", type=int, default=None, metavar="N", help="limit commit count")

    p_scan = sub.add_parser("scan", help="scan history for artifacts")
    common(p_scan)
    p_scan.add_argument("--json", action="store_true", help="machine-readable output")
    p_scan.add_argument("-o", "--output", default=None, help="also write a Markdown report")
    p_scan.set_defaults(func=cmd_scan)

    p_check = sub.add_parser("check", help="check one commit message (hook mode)")
    common(p_check, scan_args=False)
    p_check.add_argument("--msg-file", required=True, help="file containing the commit message")
    p_check.add_argument("--strict", action="store_true", help="also block warn-level rules")
    p_check.set_defaults(func=cmd_check)

    p_report = sub.add_parser("report", help="write a Markdown (+JSON) report")
    common(p_report)
    p_report.add_argument("-o", "--output", required=True, help="Markdown report path")
    p_report.add_argument("--json-output", default=None, help="also write a JSON report")
    p_report.set_defaults(func=cmd_report)

    p_hook = sub.add_parser("hook", help="install/remove/inspect the commit-msg hook")
    common(p_hook, scan_args=False)
    p_hook.add_argument("hook_cmd", choices=["install", "uninstall", "status"])
    p_hook.add_argument("--strict", action="store_true", help="hook also blocks warn-level rules")
    p_hook.add_argument(
        "--force", action="store_true", help="replace a non-aisweep hook (backs it up)"
    )
    p_hook.set_defaults(func=cmd_hook)

    p_init = sub.add_parser("init", help="write a starter .aisweep.json")
    common(p_init, scan_args=False)
    p_init.add_argument("--force", action="store_true", help="overwrite an existing config")
    p_init.set_defaults(func=cmd_init)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except GitError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    except (HookError, ConfigError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:  # pragma: no cover
        return 130
