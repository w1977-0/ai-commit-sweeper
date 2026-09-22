# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-08-31

### Added

- `aisweep scan` — audit git history for AI attribution artifacts
  (session URLs, "Generated with Claude Code" lines, AI co-author trailers),
  with `--all`, `--rev`, `--since`, `--max`, `--json` and Markdown report
  output (`-o`).
- `aisweep hook install|uninstall|status` — commit-msg hook that blocks
  polluted commits before they land (`--strict` for warn-level rules,
  `--force` to replace foreign hooks with a backup).
- `aisweep check` — check a single commit-message file (the hook's engine).
- `aisweep report` — shareable Markdown + JSON reports.
- `aisweep init` — starter `.aisweep.json` with `disable`, `severities`,
  `allow_patterns` and `extra_rules`.
- Five built-in rules, case-insensitive and line-anchored; exit codes
  documented for CI use (0 clean / 1 findings / 2 config+usage / 3 not a repo).
- Full test suite (52 tests) and CI on Python 3.10–3.13.

[0.1.0]: https://github.com/w1977-0/ai-commit-sweeper/releases/tag/v0.1.0
