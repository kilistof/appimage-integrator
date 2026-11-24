# Usage guide

## Install and start

From the repository root:

```bash
install -Dm755 appimage-integrator "$HOME/.local/bin/appimage-integrator"
"$HOME/.local/bin/appimage-integrator" --help
```

Requires Linux, Bash, and Python 3.10 or newer. `desktop-file-utils` is
recommended for validation and database updates. Runtime dependencies use only
Python's standard library. Run as your normal desktop user, without `sudo`.

Put the AppImage at its permanent location before integrating it. For example:

```bash
"$HOME/.local/bin/appimage-integrator" --id my-editor \
  "$HOME/Applications/My Editor.AppImage"
```

The `Applications` directory is an example, not a required location. The input
may be an absolute or relative path. Prefix a filename beginning with `-` with
`./`, or place it after `--`.

Only trusted type-2 AppImages are accepted. The filename extension does not
establish the format; the integrator checks the ELF and type-2 markers before
adding owner execute permission or running extraction. That permission change
is not rolled back if a later step fails.

## Confirmation and unattended use

The confirmation prompt reads from the controlling terminal. An invocation
without one needs `--yes` or `-y`:

```bash
"$HOME/.local/bin/appimage-integrator" --yes --id my-editor \
  "$HOME/Applications/My Editor.AppImage"
```

Use this only after deciding to trust the image. It does not bypass any input,
metadata, ownership, or output validation checks. See [Security](../SECURITY.md).

## Identity and updates

With the default data directory, `--id my-editor` creates:

```text
~/.local/share/applications/appimage-my-editor.desktop
~/.local/share/appimage-integrator/icons/appimage-my-editor-<hash>.<extension>
```

The icon path is used only when a supported icon is found. IDs contain 1–80
letters, digits, dots, underscores, or hyphens and start with a letter or digit.

Reuse the same ID for a replacement version:

```bash
"$HOME/.local/bin/appimage-integrator" --id my-editor \
  "$HOME/Applications/My Editor-2.0.AppImage"
```

This retargets the same managed launcher. It does not delete the older AppImage.
Without `--id`, the ID uses the first 20 hexadecimal digits of SHA-256 of the
resolved absolute path. Different versioned filenames normally produce different
IDs. This hash avoids naming collisions; it is not an integrity or trust check.

Input symlinks resolve to their target. Changing the symlink later does not
retarget the existing launcher; rerun integration with the same explicit ID.

An absolute `XDG_DATA_HOME` replaces `~/.local/share`. A relative value is ignored
with a warning. The XDG base is resolved first. Its managed `applications`,
`appimage-integrator`, and `icons` output directories must be real directories,
not symlinks. Actual paths are printed after installation.

## Desktop metadata

A root-level desktop file is preferred, with a fallback to
`usr/share/applications`. Internal symlinks are supported. If several candidates
exist, select one explicitly:

```bash
"$HOME/.local/bin/appimage-integrator" --id my-editor \
  --desktop usr/share/applications/my-editor.desktop \
  "$HOME/Applications/My Editor.AppImage"
```

The path is relative to the extracted AppDir. Traversal outside the AppDir,
absolute selection paths, and external metadata links are refused. No suitable
desktop file produces a basic launcher without assumed file or URL arguments.

Supported metadata includes names and translations, generic names, comments,
keywords, categories, MIME types, terminal behavior, and startup/window hints.
Use `--name "My Editor"` to replace the default name and any localized names.

The output sets `DBusActivatable=false` and points `TryExec` at the actual
AppImage. Working-directory paths, visibility restrictions, unknown vendor
settings, and unsupported groups are omitted. Dropped settings and unsupported
actions are reported. This produces a visible direct-launch entry rather than
a verbatim copy of the publisher's desktop file.

## Commands and desktop actions

Supported direct `Exec=program arguments...` entries are redirected to the
AppImage while preserving arguments and supported field codes. Desktop actions
are retained only when they invoke the exact same original executable as the
main command and have valid supported syntax. Retained actions use the main icon.

Known shell, `env`, interpreter, and application-manager wrappers require
command-specific handling and are rejected by the automatic rewrite. If the
application works when launched as the AppImage alone, use:

```bash
"$HOME/.local/bin/appimage-integrator" --id my-editor --simple-exec \
  "$HOME/Applications/My Editor.AppImage"
```

This intentionally removes bundled arguments, desktop actions, and MIME-type
declarations while retaining supported display metadata. It is not equivalent
to a wrapper that requires environment assignments or command arguments.
Desktop-file structure is still validated; the option does not ignore malformed
groups, duplicate keys, or non-Application entries.

Spaces, Unicode, quotes, backslashes, and shell-special characters in paths are
handled as data. For AppImage paths containing `%` or `=`, a fixed `/bin/sh`
command forwards positional arguments. The path is never evaluated as shell
source. Control characters and invalid UTF-8 in paths or custom names are
refused. Unknown or deprecated Exec field codes and unsupported quoting are
rejected rather than guessed.

## Icons

Icon discovery considers the declared icon, `.DirIcon`, conventional named-icon
locations, and deterministic root-level fallbacks. PNG, SVG, and XPM are
recognized; an extensionless `.DirIcon` can also be recognized by content.
Safe internal symlinks are followed; external or broken links are not copied.
When no supported icon exists, the launcher requests `application-x-executable`.

Icons larger than 16 MiB, unsupported formats such as SVGZ, and SVG data with
DOCTYPE or entity declarations are skipped. Identification does not render an
icon, fetch its resources, or guarantee that every desktop can display it.
Desktop files have a 1 MiB input limit. These limits do not restrict the overall
extracted AppImage size.

## Extraction and failure handling

The default extraction time limit is 300 seconds. Increase it for a large
trusted image if needed:

```bash
"$HOME/.local/bin/appimage-integrator" --timeout 900 --id my-editor \
  "$HOME/Applications/My Editor.AppImage"
```

Extraction uses a fresh private temporary directory. An existing `squashfs-root`
in the caller's directory is never reused or deleted. `TMPDIR` can select an
existing writable temporary location; enough space for the full extraction is
required. Extraction failure reports the exit status and a bounded log excerpt.

Timeout or a handled termination signal kills the extraction process group and
waits for its runtime before removing temporary files. The timeout is not a disk
or memory quota. The limits of this mechanism are explained in [Security](../SECURITY.md).

When present, `desktop-file-validate` runs before output installation. A
validation failure leaves the prior launcher unchanged. Without it, internal
checks still apply and a warning reports the skipped external validation.

Writes are serialized with a lock in the managed data directory. Existing
unmanaged launchers, unsafe locks, destination symlinks, and invalid output
directories are refused. Icon names contain content hashes; a new icon is staged
before the launcher is replaced atomically. A previous managed icon is removed
only after successful replacement and only when its path belongs to the current
ID in the managed icon directory.

Individual file replacement is atomic. The icon and launcher together are not
a power-loss-proof transaction; an interruption can leave an unused icon. A
failed optional database refresh produces a warning after installation.

## Removal

For `--id my-editor` and the default data directory:

```bash
rm -- "$HOME/.local/share/applications/appimage-my-editor.desktop"
```

Remove the exact printed icon path if it is no longer needed, then refresh the
desktop database when that utility is installed:

```bash
update-desktop-database "$HOME/.local/share/applications"
```

Use the actual output paths when `XDG_DATA_HOME` is customized. The AppImage is
left untouched. Do not remove the shared lock file while integration is running.
To remove the integrator command itself:

```bash
rm -- "$HOME/.local/bin/appimage-integrator"
```

Other tools' launchers and entries created by unrelated scripts are not migrated
or deleted automatically.

## References

- [Desktop Entry Specification: Exec](https://specifications.freedesktop.org/desktop-entry/latest/exec-variables.html)
- [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir/latest/)
- [AppImage: running and extracting AppImages](https://docs.appimage.org/user-guide/run-appimages.html)
