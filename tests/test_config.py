"""Config loading: validation errors and rule composition."""

import json

import pytest

from aisweep.config import (
    ConfigError,
    build_allow_patterns,
    build_effective_rules,
    load_config_file,
)
from aisweep.rules import DEFAULT_RULES


def test_no_config_yields_defaults():
    assert len(build_effective_rules({})) == len(DEFAULT_RULES)
    assert build_effective_rules(None) == build_effective_rules({})


def test_disable_removes_rule():
    rules = build_effective_rules({"disable": ["ai-coauthored"]})
    assert "ai-coauthored" not in {r.id for r in rules}
    assert "claude-session-url" in {r.id for r in rules}


def test_severity_override():
    rules = build_effective_rules({"severities": {"ai-coauthored": "block"}})
    rule = next(r for r in rules if r.id == "ai-coauthored")
    assert rule.severity == "block"


def test_extra_rule_is_compiled_and_applied():
    rules = build_effective_rules(
        {
            "extra_rules": [
                {
                    "id": "acme-bot",
                    "description": "deploy bot trailer",
                    "pattern": "^deployed-by: acme-bot",
                    "severity": "warn",
                }
            ]
        }
    )
    rule = next(r for r in rules if r.id == "acme-bot")
    assert rule.find("deployed-by: acme-bot\n")[0][0] == 1


def test_invalid_severity_rejected():
    with pytest.raises(ConfigError, match="severity"):
        build_effective_rules({"severities": {"ai-coauthored": "fatal"}})


def test_invalid_extra_rule_regex_rejected():
    with pytest.raises(ConfigError, match="invalid regex"):
        build_effective_rules({"extra_rules": [{"id": "x", "pattern": "("}]})


def test_invalid_allow_pattern_rejected():
    with pytest.raises(ConfigError, match="invalid regex"):
        build_allow_patterns({"allow_patterns": ["[a-"]})


def test_load_config_file(tmp_path):
    path = tmp_path / ".aisweep.json"
    path.write_text(json.dumps({"disable": ["claude-session-url"]}))
    raw = load_config_file(path)
    rules = build_effective_rules(raw)
    assert "claude-session-url" not in {r.id for r in rules}


def test_load_config_file_rejects_bad_json(tmp_path):
    path = tmp_path / ".aisweep.json"
    path.write_text("{not json")
    with pytest.raises(ConfigError, match="invalid JSON"):
        load_config_file(path)
