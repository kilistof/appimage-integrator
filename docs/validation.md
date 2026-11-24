# Validation record

## Local source validation — 24 November 2026

Version: **2.1.0**

**63 tests run: 62 passed, 1 skipped, 0 failures or errors.**
The test process exited with code 0. The full suite took 12.641 seconds in the
recorded environment; timing is informational rather than a performance promise.

The skipped case, `test_root_execution_refused`, requires a root test runner.
This run used an ordinary user. The workflow contains a separate step for that
case, but its hosted execution is not part of this local result.

### Environment

| Component | Value |
| --- | --- |
| Distribution | Debian GNU/Linux 13 (trixie) |
| Architecture | x86_64 |
| Python | 3.12.14 |
| Bash | 5.2.37 |
| C compiler | GCC 14.2.0 |
| GLib/GIO | 2.84.4 |
| `desktop-file-validate` | Available and exercised |
| `update-desktop-database` | Available and exercised |
| ShellCheck | Unavailable locally; configured in CI |

### Coverage

The suite exercises the public command and independently parses generated
desktop entries. It does not import the program's private parser functions.

- Input validation before permission or installation changes.
- Main commands, arguments, field codes, names, translations, and desktop actions.
- Explicit desktop selection, basic fallback, unsupported wrappers, and
  `--simple-exec` behavior.
- Icon formats, `.DirIcon`, internal links, and rejection of external links.
- XDG output locations, stable IDs, version updates, and unmanaged-file protection.
- Extraction errors, timeout, SIGTERM, temporary cleanup, and preservation of an
  existing caller-owned `squashfs-root`.
- Interactive trust acceptance and rejection with a controlling terminal.
- Unsafe output directories, symlinks, lock files, and FIFO-lock refusal.
- Validation and database-refresh failure paths using controlled helper stubs.

Four GIO tests actually launch the harmless fixture through generated desktop
entries. They check URI and local-file arguments, quoted arguments, a desktop
action, Unicode, percent and equals signs, and shell-looking filenames remaining
inert data. Ordinary installation tests use the real desktop-file validator.

Bash syntax and embedded Python compilation passed. Focused checks also verified
test invocation from a different working directory, an explicit extensionless
executable path, and selection of an individual unittest case.

### Exact source snapshot

| File | SHA-256 |
| --- | --- |
| `appimage-integrator` | `27781e7f8b61bdbbbb2c8effb99133c2b792777141208d2cdb72f6162515c167` |
| `tests/test_appimage_integrator.py` | `37d8db27c13fb5c41c96a421282cff6b75b046d02c0c5df6f17eb3b6fd837f1b` |

These identify the tested source snapshot. Later edits require fresh validation;
the table is not an automatically updated checksum manifest.

## Repository configuration checks

The workflow and issue-form YAML parsed successfully. Structural checks verified
the workflow events, read-only permissions, matrix, checkout pin, and issue-form
fields. Shell blocks in the workflow passed `bash -n`. Repository document links,
source packaging, executable permissions, and publication-specific text were
checked while preparing this directory.

The workflow uses a full commit pin for `actions/checkout` and disables credential
persistence. Dependabot is configured to propose GitHub Actions updates. These
configuration checks do not establish that GitHub has accepted or run a workflow.

## Hosted checks

[CI](../.github/workflows/ci.yml) is prepared for Ubuntu 22.04 and Ubuntu 24.04,
using the system Python in each image. It installs test tools, runs Bash syntax
and ShellCheck, executes the full ordinary-user suite, and separately verifies
root refusal.

**The hosted workflow has not been executed as part of this validation.** Inspect
its actual result after pushing to GitHub. ShellCheck and actionlint were not
available for this local preparation. Runner availability and preinstalled
software can change; maintain the matrix when GitHub retires an image.

## Practical limits

The fixture is a compiled ELF with an AppImage type-2 format marker and simulated
extraction. It contains no real SquashFS payload. No third-party AppImage,
application GUI, FUSE mounting, graphical menu discovery, or icon rendering was
tested. The Debian fixture run does not establish universal distribution or
desktop compatibility.

To repeat the behavioral suite from the repository root:

```bash
python3 tests/test_appimage_integrator.py
```

See [Contributing](../CONTRIBUTING.md) for dependencies and additional checks.
