"""Render scan results as Markdown or JSON."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from .scanner import MAX_EXCERPT, ScanResult


def _cell(text: str) -> str:
    """Make a string safe inside a Markdown table cell."""
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("`", "'").strip()


def render_markdown(result: ScanResult) -> str:
    """Render a human-reviewable Markdown report."""
    lines: list[str] = [
        "# aisweep report",
        "",
        f"- Repository: `{result.repository}`",
        f"- Range: `{result.range}`",
        f"- Commits scanned: {result.commits_scanned}",
        f"- Findings: {len(result.findings)}"
        f" (in {result.commits_with_findings} commit(s))",
        f"- Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "",
    ]
    if result.findings:
        lines += [
            "| Commit | Date | Author | Rule | Severity | Artifact |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for f in result.findings:
            artifact = _cell(f.excerpt(MAX_EXCERPT))
            lines.append(
                f"| `{_cell(f.short)}` | {_cell(f.date)} | {_cell(f.author)} "
                f"| `{_cell(f.rule_id)}` | {_cell(f.severity)} | `{artifact}` |"
            )
        lines += [
            "",
            "Prevent future artifacts inside this repository with `aisweep hook install`.",
        ]
    else:
        lines += ["No AI attribution artifacts found. ✨"]
    return "\n".join(lines) + "\n"


def render_json(result: ScanResult) -> str:
    """Render a machine-readable JSON report."""
    return json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
