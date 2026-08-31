# Security Policy

## Supported versions

| Version | Supported |
| --- | --- |
| 0.1.x | ✅ |

## Reporting a vulnerability

Please report vulnerabilities privately via GitHub's
**Report a vulnerability** button on the
[Security tab](https://github.com/w1977-0/aisweep/security) of this
repository. Do not open a public issue for anything you believe is
exploitable.

You can expect an initial response within 7 days and a fix or a mitigation
plan within 30 days for accepted reports.

## Scope notes

- aisweep is a **local, offline tool**: it runs `git` commands on
  repositories you point it at and makes no network requests of its own. If
  you find a way to make it exfiltrate data or execute unintended commands
  (for example via a crafted repository, config file or hook path), that is a
  reportable vulnerability.
- **Found secrets or sensitive data in your own commit history while scanning?**
  That is a finding about *your repository*, not about aisweep — handle it
  locally (rotate the credential, purge history with git-filter-repo). Please
  do not paste other people's secrets into public issues.

## Safe usage notes

- The commit-msg hook executes `python -m aisweep` with the interpreter it was
  installed with; if you move or rename a virtualenv, re-run
  `aisweep hook install`.
- Hook installation never silently replaces an existing hook it did not write;
  `--force` creates a `.bak-aisweep` backup first.
