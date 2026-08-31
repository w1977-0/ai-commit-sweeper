"""CLI behaviour: exit codes, output formats, config discovery."""

import json

from aisweep.cli import main
from tests.conftest import DIRTY_MESSAGE, WARN_ONLY_MESSAGE


def test_scan_clean_repo_exit_zero(repo, capsys):
    repo.commit("chore: initial import")
    assert main(["scan", "--repo", str(repo.path), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["commits_scanned"] == 1
    assert data["findings"] == []


def test_scan_dirty_repo_exit_one(repo, capsys):
    repo.commit(DIRTY_MESSAGE)
    assert main(["scan", "--repo", str(repo.path), "--json"]) == 1
    data = json.loads(capsys.readouterr().out)
    assert len(data["findings"]) == 3


def test_scan_human_output(repo, capsys):
    repo.commit(DIRTY_MESSAGE)
    assert main(["scan", "--repo", str(repo.path)]) == 1
    out = capsys.readouterr().out
    assert "claude-session-url" in out
    assert "1/1 commit(s) contain" in out


def test_scan_non_repo_exit_three(tmp_path, capsys):
    assert main(["scan", "--repo", str(tmp_path)]) == 3
    assert "not a git repository" in capsys.readouterr().err


def test_report_writes_markdown_and_json(repo, tmp_path):
    repo.commit(DIRTY_MESSAGE)
    out_md = tmp_path / "report.md"
    out_json = tmp_path / "report.json"
    assert main(
        ["report", "--repo", str(repo.path), "-o", str(out_md), "--json-output", str(out_json)]
    ) == 1
    md = out_md.read_text()
    assert "# aisweep report" in md
    assert "claude-session-url" in md
    data = json.loads(out_json.read_text())
    assert len(data["findings"]) == 3


def test_check_file(repo, tmp_path):
    msg = tmp_path / "msg.txt"
    msg.write_text(DIRTY_MESSAGE)
    assert main(["check", "--repo", str(repo.path), "--msg-file", str(msg)]) == 1

    msg.write_text(WARN_ONLY_MESSAGE)
    assert main(["check", "--repo", str(repo.path), "--msg-file", str(msg)]) == 0
    assert main(["check", "--repo", str(repo.path), "--msg-file", str(msg), "--strict"]) == 1


def test_hook_status_and_init(repo, capsys):
    assert main(["hook", "status", "--repo", str(repo.path)]) == 0
    assert "not installed" in capsys.readouterr().out

    assert main(["init", "--repo", str(repo.path)]) == 0
    assert (repo.path / ".aisweep.json").exists()
    assert main(["init", "--repo", str(repo.path)]) == 2


def test_config_discovered_from_repo(repo, tmp_path, capsys):
    (repo.path / ".aisweep.json").write_text(json.dumps({"disable": ["claude-session-url"]}))
    repo.commit(DIRTY_MESSAGE)
    assert main(["scan", "--repo", str(repo.path), "--json"]) == 1
    data = json.loads(capsys.readouterr().out)
    assert {f["rule_id"] for f in data["findings"]} == {
        "claude-generated-with",
        "claude-coauthored",
    }
