"""Configuration loading for aisweep.

Configuration lives in ``.aisweep.json`` at the repository root (or in a file
passed with ``--config``). It is intentionally dependency-free JSON so the
tool stays stdlib-only. Recognised keys:

.. code-block:: json

    {
      "disable": ["ai-coauthored"],
      "severities": {"ai-coauthored": "block"},
      "allow_patterns": ["^co-authored-by:.*\\bmy-own-claude\\b"],
      "extra_rules": [
        {
          "id": "acme-deploy-bot",
          "description": "Our deploy bot trailer",
          "pattern": "^deployed-by: acme-bot",
          "severity": "warn"
        }
      ]
    }

* ``disable`` — IDs of built-in rules to switch off.
* ``severities`` — per-rule severity overrides (``block`` or ``warn``).
* ``allow_patterns`` — regexes; a matching line never produces a finding.
* ``extra_rules`` — additional rules, compiled exactly like the built-ins.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .rules import DEFAULT_RULES, SEVERITIES, Rule

CONFIG_FILENAME = ".aisweep.json"


class ConfigError(ValueError):
    """Raised when a configuration file is invalid."""


def _parse_rule(spec: object, index: int) -> Rule:
    if not isinstance(spec, dict):
        raise ConfigError(f"extra_rules[{index}] must be an object")
    try:
        rule_id = spec["id"]
        raw_pattern = spec["pattern"]
    except KeyError as exc:
        raise ConfigError(f"extra_rules[{index}] is missing required key {exc}") from exc
    if not isinstance(rule_id, str) or not rule_id:
        raise ConfigError(f"extra_rules[{index}].id must be a non-empty string")
    if not isinstance(raw_pattern, str):
        raise ConfigError(f"extra_rules[{index}].pattern must be a string")
    try:
        pattern = re.compile(raw_pattern, re.M | re.I)
    except re.error as exc:
        raise ConfigError(f"extra_rules[{index}].pattern: invalid regex ({exc})") from exc
    severity = spec.get("severity", "block")
    if severity not in SEVERITIES:
        raise ConfigError(
            f"extra_rules[{index}].severity must be one of {', '.join(SEVERITIES)}"
        )
    description = spec.get("description", "")
    if not isinstance(description, str):
        raise ConfigError(f"extra_rules[{index}].description must be a string")
    return Rule(id=rule_id, description=description, pattern=pattern, severity=severity)


def _compile_allow(spec: object, index: int) -> re.Pattern[str]:
    if not isinstance(spec, str):
        raise ConfigError(f"allow_patterns[{index}] must be a string")
    try:
        return re.compile(spec)
    except re.error as exc:
        raise ConfigError(f"allow_patterns[{index}]: invalid regex ({exc})") from exc


def _validate(raw: object) -> dict:
    if not isinstance(raw, dict):
        raise ConfigError("top level of the config must be a JSON object")
    for key, value in raw.items():
        if key in {"disable", "allow_patterns", "extra_rules"} and not isinstance(value, list):
            raise ConfigError(f"{key!r} must be a list")
        if key == "severities":
            if not isinstance(value, dict):
                raise ConfigError("'severities' must be an object")
            for rule_id, severity in value.items():
                if severity not in SEVERITIES:
                    raise ConfigError(
                        f"severities[{rule_id!r}]: severity must be one of {', '.join(SEVERITIES)}"
                    )
    return raw


def _apply(raw: dict, rules: list[Rule]) -> tuple[Rule, ...]:
    severities: dict = raw.get("severities", {})
    disabled: set = set(raw.get("disable", []))
    effective: list[Rule] = []
    for rule in rules:
        if rule.id in disabled:
            continue
        if rule.id in severities:
            rule = Rule(
                id=rule.id,
                description=rule.description,
                pattern=rule.pattern,
                severity=severities[rule.id],
            )
        effective.append(rule)
    return tuple(effective)


def build_effective_rules(raw: dict | None) -> tuple[Rule, ...]:
    """Return the effective ruleset: defaults + ``extra_rules`` minus ``disable``."""
    raw = _validate(raw or {})
    rules: list[Rule] = list(DEFAULT_RULES)
    for i, spec in enumerate(raw.get("extra_rules", [])):
        rules.append(_parse_rule(spec, i))
    return _apply(raw, rules)


def build_allow_patterns(raw: dict | None) -> tuple[re.Pattern[str], ...]:
    """Return compiled allowlist patterns from a raw config mapping."""
    raw = _validate(raw or {})
    return tuple(_compile_allow(spec, i) for i, spec in enumerate(raw.get("allow_patterns", [])))


def load_config_file(path: Path) -> dict:
    """Load and validate ``path``; raise :class:`ConfigError` on any problem."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"cannot read config {path}: {exc}") from exc
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"invalid JSON in {path}: {exc}") from exc
    return _validate(raw)


def load_config(repo_root: Path | None, explicit: Path | None = None) -> dict:
    """Return the raw config mapping for a repository.

    ``explicit`` wins; otherwise ``<repo_root>/.aisweep.json`` if present;
    otherwise an empty mapping.
    """
    if explicit is not None:
        return load_config_file(explicit)
    if repo_root is not None:
        candidate = repo_root / CONFIG_FILENAME
        if candidate.is_file():
            return load_config_file(candidate)
    return {}
