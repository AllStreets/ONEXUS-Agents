# Security Policy

## Reporting a vulnerability

Please report security issues privately via GitHub's
[private vulnerability reporting](https://github.com/AllStreets/ONEXUS-Agents/security/advisories/new)
or by emailing connorevans29@gmail.com.

We will acknowledge within 72 hours and aim to patch within 14 days.

Please do not open a public issue for security problems.

## Scope

This repository is a public agent catalog that runs scheduled bots with
repository secrets. Of particular interest:

- The submission workflow (`.github/workflows/submission.yml`), which
  processes untrusted issue content into catalog entries.
- The nightly and weekly pipeline workflows, which hold API credentials.
- The published catalog data consumed by downstream runtimes.
