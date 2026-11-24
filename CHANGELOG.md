# Changelog

## 2.1.0 — 2026-11-24

- Prepared the public repository layout with a single executable, documentation,
  regression tests, MIT license, and GitHub workflow.
- Added user-local integration for trusted type-2 AppImages, using XDG data paths.
- Included stable update IDs, supported desktop metadata and action preservation,
  explicit desktop-file selection, and a simple-command fallback.
- Included isolated temporary extraction, a configurable 300-second timeout,
  interruption cleanup, output ownership checks, and atomic file replacement.
- Included optional desktop-file validation and database refresh.
- Recorded local validation separately from future hosted CI results.

The public version uses the same integration behavior as its prepared source
baseline; the repository organization does not change the command-line options.
