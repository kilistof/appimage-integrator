# AppImage Integrator

Add trusted type-2 AppImages to your Linux application menu with a single
command. AppImage Integrator extracts desktop metadata and an icon, then creates
a launcher for your user account. Your AppImage stays in its existing location.

**Version:** 2.1.0 · **License:** [MIT](LICENSE) · **Runtime:** Bash + Python 3.10+

## Features

- Installs user-local launchers using standard XDG data directories.
- Preserves supported names, translations, launch arguments, and desktop actions.
- Handles spaces, Unicode, and special characters in AppImage paths.
- Uses an isolated temporary extraction directory and a configurable timeout.
- Supports stable application IDs so new versions replace the same launcher.
- Validates desktop entries when `desktop-file-utils` is installed.
- Protects existing unmanaged launchers and writes updates atomically.

**Use only AppImages you trust.** Extraction executes the AppImage runtime with
your user permissions. The format check is not authentication or a sandbox.
Run the integrator as your normal user, without `sudo`.

## Requirements

- Linux and Bash.
- Python 3.10 or newer, available as `python3`; no third-party Python packages.
- A type-2 AppImage suitable for your computer.
- Recommended: `desktop-file-utils` for launcher validation and database updates.

On Arch Linux or CachyOS, install the dependencies using your usual package
management workflow. For example, this also performs a full system update:

```bash
sudo pacman -Syu --needed python desktop-file-utils
```

Other distributions can use their package manager to provide the same tools.
See [compatibility](docs/compatibility.md) for runtime and desktop limitations.

## Install

Download or clone the repository, open a terminal in its root directory, and run:

```bash
install -Dm755 appimage-integrator "$HOME/.local/bin/appimage-integrator"
```

There is no build step. The full path works even when `~/.local/bin` is not in
your `PATH`. The script selects Bash itself, so it can also be invoked from Fish
or another interactive shell.

## Use

Place the AppImage in its permanent location, then integrate it:

```bash
"$HOME/.local/bin/appimage-integrator" --id my-app \
  "$HOME/Applications/My App.AppImage"
```

Replace the example path with your actual file. The script asks you to confirm
that you trust the AppImage before extraction. For a later version, reuse the ID:

```bash
"$HOME/.local/bin/appimage-integrator" --id my-app \
  "$HOME/Applications/My App-2.0.AppImage"
```

The old AppImage is not deleted. Input symlinks resolve to their targets; rerun
integration after changing a target. Generated launchers contain absolute local
paths, so integrate separately on each computer.

| Option | Purpose |
| --- | --- |
| `--id ID` | Keep a stable launcher identity across application updates. |
| `--name NAME` | Override the displayed name and its translations. |
| `--desktop RELATIVE_PATH` | Select one embedded desktop file when several exist. |
| `--simple-exec` | Launch the AppImage without bundled arguments, actions, or MIME declarations. |
| `--timeout SECONDS` | Set the extraction limit; default 300 seconds. |
| `--yes`, `-y` | Skip the trust prompt for a file you have already decided to trust. |

Run `appimage-integrator --help` for command help. The [usage guide](docs/usage.md)
covers output locations, metadata, unusual commands, updates, and removal.

## Test

From the repository root:

```bash
python3 tests/test_appimage_integrator.py
```

Tests require a C compiler. GIO checks also need `libgio-2.0`; the test suite
reports missing prerequisites as skips. Tests compile a harmless ELF fixture
and simulate extraction in temporary directories. They do not download or run
a third-party AppImage.

The [validation record](docs/validation.md) distinguishes local results from
the prepared GitHub Actions workflow. The workflow checks Ubuntu 22.04 and
24.04 using their system Python, Bash syntax, ShellCheck, desktop validation,
fixture launches, and a dedicated root-refusal test.

## Project information

- [Usage guide](docs/usage.md)
- [Distribution compatibility](docs/compatibility.md)
- [Contributing and development](CONTRIBUTING.md)
- [Security boundaries and reporting](SECURITY.md)
- [Changelog](CHANGELOG.md)
- [Publishing this directory on GitHub](docs/publishing.md)

## License

[MIT](LICENSE), with project-level attribution to AppImage Integrator contributors.
