"""Scanner behaviour against real throwaway git repositories."""

import pytest

from aisweep.scanner import GitError, scan
from tests.conftest import CLEAN_MESSAGE, DIRTY_MESSAGE, WARN_ONLY_MESSAGE


def test_scan_finds_artifacts_in_dirty_commit(repo):
    repo.commit(CLEAN_MESSAGE)
    dirty_sha = repo.commit(DIRTY_MESSAGE)
    repo.commit(CLEAN_MESSAGE)

    result = scan(repo.path, {})
    assert result.commits_scanned == 3
    assert len(result.findings) == 3
    assert {f.rule_id for f in result.findings} == {
        "claude-generated-with",
        "claude-coauthored",
        "claude-session-url",
    }
    assert {f.commit for f in result.findings} == {dirty_sha}
    assert result.commits_with_findings == 1


def test_scan_range_options(repo):
    repo.commit(DIRTY_MESSAGE)
    repo.commit(CLEAN_MESSAGE)

    limited = scan(repo.path, {}, max_count=1)
    assert limited.commits_scanned == 1
    assert limited.findings == []

    deep = scan(repo.path, {}, rev="HEAD~1")
    assert deep.commits_scanned == 1
    assert len(deep.findings) == 3

    whole = scan(repo.path, {}, all_branches=True)
    assert whole.commits_scanned == 2
    assert len(whole.findings) == 3


def test_scan_warn_only_message(repo):
    repo.commit(WARN_ONLY_MESSAGE)
    result = scan(repo.path, {})
    assert [f.rule_id for f in result.findings] == ["ai-coauthored"]
    assert all(f.severity == "warn" for f in result.findings)


def test_scan_respects_config(repo):
    repo.commit(DIRTY_MESSAGE)
    result = scan(repo.path, {"disable": ["claude-session-url"]})
    assert "claude-session-url" not in {f.rule_id for f in result.findings}
    assert len(result.findings) == 2


def test_scan_empty_repo(tmp_path):
    import subprocess

    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(tmp_path)],
        check=True,
        capture_output=True,
    )
    result = scan(tmp_path, {})
    assert result.commits_scanned == 0
    assert result.findings == []


def test_scan_non_repo_raises(tmp_path):
    with pytest.raises(GitError, match="not a git repository"):
        scan(tmp_path, {})


def test_scan_result_serializes(repo):
    import json

    repo.commit(DIRTY_MESSAGE)
    result = scan(repo.path, {})
    data = json.loads(json.dumps(result.to_dict()))
    assert data["commits_scanned"] == 1
    assert data["findings"][0]["rule_id"] == "claude-session-url"
    assert data["range"] == "main"
