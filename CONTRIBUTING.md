# Contributing

## Development setup

AppImage Integrator is a Bash entry point containing a Python standard-library
program. There is no package installation or dependency resolution step for
development. Use Linux, Bash, Python 3.10 or newer, and a C compiler (`cc` or `gcc`).
Install `desktop-file-utils`, the system GLib/GIO library, and ShellCheck to run
the full set of local checks.

Run these commands from the repository root:

```bash
bash -n appimage-integrator
shellcheck appimage-integrator
python3 tests/test_appimage_integrator.py
```

The regression suite locates the executable relative to its own file. It also
accepts an explicit executable path and normal `unittest` selections:

```bash
python3 tests/test_appimage_integrator.py ./appimage-integrator
python3 tests/test_appimage_integrator.py InvocationTests
```

The root-refusal test is skipped for an ordinary test runner. CI invokes that
one test separately as root; the normal suite runs as an ordinary user. A skip
is not a pass. Report missing compiler, GIO, or validator prerequisites when
describing results.

## Changing behavior

Keep changes focused and explain the concrete problem, resulting behavior, and
validation performed. Add a behavioral regression when fixing a defect that
the existing suite would otherwise miss. Avoid tests that simply duplicate an
implementation detail.

Preserve the public CLI and existing managed launcher ownership marker unless a
change explicitly includes a migration plan. Keep installation user-local and
retain refusal to overwrite unrelated launchers. Treat desktop metadata and
filenames as data; do not interpolate them into shell source.

Do not use a downloaded AppImage as an automated test fixture. The included
fixture is compiled from source during the test run, performs controlled
extraction, and records arguments in temporary directories. A genuine AppImage
may be tested manually only when its source is trusted; document that result
separately from fixture tests.

## Reporting bugs

Include the integrator version, distribution and version, desktop environment,
Python version, relevant command, expected result, and actual error. A small
sanitized desktop entry is often more useful than a full application bundle.
Remove private filenames, user data, and credentials from reports.

For vulnerabilities, follow [SECURITY.md](SECURITY.md).

## Documentation and licensing

Use relative links for repository documents and keep examples independent of
maintainer usernames or computer paths. Source and documentation are distributed
under the [MIT license](LICENSE); include the same license context with changes.
Do not add third-party code or assets without preserving their applicable terms.
