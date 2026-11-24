# Compatibility

## Intended environment

The integrator targets ordinary Linux desktop environments that support XDG
user data directories and freedesktop.org desktop entries. It requires Bash
and Python 3.10 or newer. The code does not call a distribution package manager
or depend on Arch-specific paths.

Ubuntu, Debian, Linux Mint, Fedora, openSUSE, Arch Linux, and CachyOS are plausible
targets when these prerequisites are available. This is an assessment of the
design, not a claim that all those distributions have been tested. The prepared
CI workflow uses Ubuntu 22.04 and 24.04; actual local results are recorded in
[validation](validation.md).

## Integration and application execution

Creating a valid launcher does not prove that the application itself can run.
The AppImage must match the CPU architecture and satisfy its own library,
graphics, FUSE, and sandbox requirements. The integrator does not install FUSE,
change application sandbox settings, or set default MIME handlers.

An AppImage may extract successfully even when normal launching fails because
its FUSE requirements are unmet. Different runtimes and distribution releases
need different setup; follow the [official AppImage FUSE guidance](https://docs.appimage.org/user-guide/troubleshooting/fuse.html).

Only type-2 AppImages with the standard ELF marker are supported. Legacy type-1
images and arbitrary portable executables are rejected. Full extraction requires
temporary disk space. Executable files must be on a filesystem that allows
execution by the current user.

## NixOS and nonstandard environments

AppImages often assume library paths absent from a default NixOS installation.
The NixOS project documents `appimage-run` and AppImage binary-format support in
its [official wiki](https://wiki.nixos.org/wiki/Appimage).

This integrator directly invokes the AppImage for extraction and creates a
launcher that invokes it again. It does not automatically configure an NixOS
runtime wrapper or guarantee compatibility with those mechanisms. Verify the
particular application's extraction and launch behavior in that environment.

Containers, minimal window managers, and systems without a graphical session
can run suitable parts of the tool but may have no application menu to update.
Desktop-specific icon rendering, menu refresh timing, and advanced action
behavior can differ.

## Multiple computers

Copy the source tool between computers and run integration on each one. Use
consistent explicit application IDs if desired. Generated desktop files contain
absolute local paths, so copying them between machines with different home or
application locations can break the launcher.

The integrator resolves an input symlink when creating the entry. Updating the
symlink afterward does not update the entry; rerun with the same ID.

## Evidence limits

The automated suite compiles an ELF fixture containing a type-2 marker and
simulates extraction. It uses real desktop-file validation and GIO launching
when those components are present. These checks verify parsing and integration
behavior but do not substitute for testing a genuine AppImage, FUSE mounting,
or graphical menu discovery on the target desktop.
