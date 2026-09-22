# Contributing to aisweep

Thanks for helping make AI-assisted commits cleaner. Contributions of all
sizes are welcome: bug reports, documentation fixes, new detection rules,
tooling.

## Ways to contribute

- **Bug report** — open a [bug issue](.github/ISSUE_TEMPLATE/bug_report.yml)
  with steps to reproduce.
- **Feature idea** — open a
  [feature request](.github/ISSUE_TEMPLATE/feature_request.yml) describing the
  problem first; the Roadmap in the README tracks what is planned.
- **Code** — fork/branch, change, test, PR (details below).

## Development setup

```bash
git clone https://github.com/w1977-0/ai-commit-sweeper.git && cd ai-commit-sweeper
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
```

Prerequisites: Python 3.10+, git ≥ 2.28.

## Before you open a PR

```bash
pytest                 # all tests must pass
ruff check aisweep tests   # no lint findings
```

CI runs the same checks on Python 3.10–3.13 and builds the package. A PR that
makes coverage of a new behaviour explicit (a test) is much easier to accept.

If your change is user-facing (new flag, new rule, changed exit codes), add a
line under the *Unreleased* section of `CHANGELOG.md`.

## Branch and commit conventions

- `main` is protected; work on feature branches (`feature/<short-name>`,
  `fix/<short-name>`) and open a PR against `main`.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/):

  ```text
  feat: add --since filter to scan
  fix(rule): anchor claude-session-url to message start
  docs: translate FAQ to Chinese
  test: cover hook --force backup path
  chore(ci): pin actions by SHA
  ```

- Keep PRs small and focused — one behaviour per PR.

## Reporting bugs well

Include: `aisweep --version`, Python and git versions, OS, the exact command,
the output (redact anything private), and what you expected instead. If the
bug involves a specific commit message shape, a minimal reproduction in a
throwaway repo is the fastest path to a fix.

## Adding a detection rule

Rules must match a **documented, reproducible artifact shape** — link the
issue, docs page or discussion that shows the shape, add positive *and*
negative samples to `tests/test_rules.py`, and prefer `warn` over `block` for
anything that could hit a legitimate human message. Vague "AI smells" patterns
will not be accepted.

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). By
participating you are expected to uphold it.
