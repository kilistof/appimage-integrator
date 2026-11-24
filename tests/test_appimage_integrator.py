#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent behavioral tests for AppImage Integrator.

Run from the repository root:
    python3 tests/test_appimage_integrator.py [path/to/appimage-integrator]

The default executable is resolved relative to this file, so invocation from
another working directory also works. Standard unittest test-name arguments
remain available, for example IntegrationTests.test_root_execution_refused.

Requires Linux, Bash, Python 3.10+ and a C compiler (cc or gcc). GIO launch tests
are skipped when libgio-2.0 is unavailable. The root-only refusal test is skipped
for an ordinary user; when run as root, installation subprocesses drop to nobody.

The compiled ELF fixture carries an AppImage type-2 format marker, but has NO
SquashFS payload. It simulates extraction into temporary homes; these tests do
not establish compatibility with a genuine AppImage or a graphical desktop.
"""

from __future__ import annotations

import base64
import configparser
import ctypes.util
import hashlib
import json
import os
from pathlib import Path
import pty
import pwd
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "appimage-integrator"
if len(sys.argv) > 1 and not sys.argv[1].startswith("-") and (
        "/" in sys.argv[1] or sys.argv[1].endswith(".sh")
        or Path(sys.argv[1]).expanduser().is_file()):
    SCRIPT = Path(sys.argv.pop(1)).expanduser().resolve()
BASH = shutil.which("bash")
GIO_AVAILABLE = bool(ctypes.util.find_library("gio-2.0"))
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/"
    "x8AAwMCAO+aF1cAAAAASUVORK5CYII="
)
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"><rect width="16" height="16"/></svg>'
XPM = b'/* XPM */\nstatic char *icon[] = {"1 1 1 1", ". c #000000", "."};\n'
DESKTOP = """[Desktop Entry]
Type=Application
Name=Fixture Editor
Name[de]=Testeditor
GenericName=Editor
Comment=Regression test application
Keywords=Editor;Tests;
Exec=fixture --flag %U
TryExec=native-fixture-missing
Icon=fixture
Terminal=false
DBusActivatable=true
Path=/unavailable/native/path
Categories=Utility;
MimeType=text/plain;
StartupWMClass=FixtureEditor
Actions=New;Other;

[Desktop Action New]
Name=New Window
Exec=fixture --new-window %U

[Desktop Action Other]
Name=Unsupported helper
Exec=unrelated-helper --special
"""

FIXTURE_PYTHON = r'''
import json
import os
from pathlib import Path
import shutil
import sys
import time

if sys.argv[1:] == ["--appimage-extract"]:
    marker = Path(os.environ["FIXTURE_EXTRACT_MARKER"])
    marker.write_text(json.dumps({
        "cwd": str(Path.cwd()),
        "pid": os.getpid(),
        "runtime_environment": {
            key: os.environ.get(key)
            for key in ("TARGET_APPIMAGE", "APPIMAGE", "APPDIR", "ARGV0",
                        "APPIMAGE_EXTRACT_AND_RUN")
        },
    }))
    mode = os.environ.get("FIXTURE_MODE", "ok")
    if mode == "sleep":
        time.sleep(60)
    elif mode == "fail":
        Path("squashfs-root").mkdir()
        Path("squashfs-root/partial.txt").write_text("partial extraction")
        print("controlled extraction failure", file=sys.stderr)
        raise SystemExit(23)
    elif mode == "missing":
        raise SystemExit(0)
    elif mode == "symlink-root":
        Path("squashfs-root").symlink_to(os.environ["FIXTURE_TREE"])
        raise SystemExit(0)
    shutil.copytree(os.environ["FIXTURE_TREE"], "squashfs-root", symlinks=True)
else:
    result = Path(os.environ["FIXTURE_LAUNCH_OUTPUT"])
    temporary = result.with_suffix(".pending")
    temporary.write_text(json.dumps({
        "image": os.environ["FIXTURE_SELF"],
        "arguments": sys.argv[1:],
    }))
    os.replace(temporary, result)
'''

C_FIXTURE = r'''
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

int main(int argc, char **argv) {
    char *extractor = getenv("FIXTURE_EXTRACTOR");
    if (extractor == NULL) return 91;
    if (setenv("FIXTURE_SELF", argv[0], 1)) return 92;
    char **args = calloc((size_t)argc + 2, sizeof(char *));
    if (args == NULL) return 93;
    args[0] = PYTHON_EXECUTABLE;
    args[1] = extractor;
    for (int i = 1; i < argc; ++i) args[i + 1] = argv[i];
    execv(PYTHON_EXECUTABLE, args);
    perror("fixture execv");
    return 94;
}
'''

GIO_LAUNCH = r'''
import ctypes as C
import json
import sys

gio = C.CDLL("libgio-2.0.so.0")
glib = C.CDLL("libglib-2.0.so.0")
gobject = C.CDLL("libgobject-2.0.so.0")
gio.g_desktop_app_info_new_from_filename.argtypes = [C.c_char_p]
gio.g_desktop_app_info_new_from_filename.restype = C.c_void_p
gio.g_app_info_launch_uris.argtypes = [
    C.c_void_p, C.c_void_p, C.c_void_p, C.POINTER(C.c_void_p)
]
gio.g_app_info_launch_uris.restype = C.c_int
gio.g_desktop_app_info_launch_action.argtypes = [
    C.c_void_p, C.c_char_p, C.c_void_p
]
glib.g_list_append.argtypes = [C.c_void_p, C.c_void_p]
glib.g_list_append.restype = C.c_void_p
glib.g_list_free.argtypes = [C.c_void_p]
gobject.g_object_unref.argtypes = [C.c_void_p]
info = gio.g_desktop_app_info_new_from_filename(sys.argv[1].encode())
if not info:
    raise SystemExit("GIO rejected the generated desktop entry")
try:
    if sys.argv[2] == "action":
        gio.g_desktop_app_info_launch_action(info, sys.argv[3].encode(), None)
    else:
        uri_list = None
        buffers = [C.create_string_buffer(value.encode())
                   for value in json.loads(sys.argv[3])]
        for buffer in buffers:
            uri_list = glib.g_list_append(uri_list, C.cast(buffer, C.c_void_p))
        error = C.c_void_p()
        result = gio.g_app_info_launch_uris(info, uri_list, None, C.byref(error))
        glib.g_list_free(uri_list)
        if not result:
            class GError(C.Structure):
                _fields_ = [("domain", C.c_uint), ("code", C.c_int),
                            ("message", C.c_char_p)]
            detail = C.cast(error, C.POINTER(GError)).contents.message.decode() if error else "unknown error"
            raise SystemExit("GIO launch failed: " + detail)
finally:
    gobject.g_object_unref(info)
'''


def desktop_groups(path: Path) -> dict[str, dict[str, str]]:
    """Independent parser for generated entries; no integrator code is imported."""
    parser = configparser.ConfigParser(
        interpolation=None, delimiters=("=",), strict=True
    )
    parser.optionxform = str
    with path.open(encoding="utf-8") as stream:
        parser.read_file(stream)
    return {section: dict(parser[section]) for section in parser.sections()}


def desktop_unescape(value: str) -> str:
    mapping = {"s": " ", "n": "\n", "r": "\r", "t": "\t", "\\": "\\"}
    decoded = []
    index = 0
    while index < len(value):
        char = value[index]
        if char == "\\":
            index += 1
            char = mapping[value[index]]
        decoded.append(char)
        index += 1
    return "".join(decoded)


class InvocationTests(unittest.TestCase):
    def test_bash_syntax(self):
        result = subprocess.run(
            [BASH, "-n", str(SCRIPT)], text=True, capture_output=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_help_documents_supported_cli(self):
        result = subprocess.run(
            [BASH, str(SCRIPT), "--help"], text=True, capture_output=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        for option in ("--id", "--name", "--desktop", "--simple-exec", "--yes",
                       "--timeout"):
            with self.subTest(option=option):
                self.assertIn(option, result.stdout)

    def test_version_identifies_release(self):
        result = subprocess.run(
            [BASH, str(SCRIPT), "--version"], text=True, capture_output=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "2.1.0")

    def test_missing_argument_fails(self):
        result = subprocess.run(
            [BASH, str(SCRIPT)], text=True, capture_output=True
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("usage:", result.stderr.lower())


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if sys.platform != "linux":
            raise unittest.SkipTest("Linux is required for the ELF fixture.")
        compiler = shutil.which("cc") or shutil.which("gcc")
        if not compiler:
            raise unittest.SkipTest("A C compiler is required for the fixture.")
        cls.build_directory = tempfile.TemporaryDirectory(
            prefix="appimage-regression-build-"
        )
        cls.build = Path(cls.build_directory.name)
        cls.build.chmod(0o755)
        fixture_source = cls.build / "fixture.c"
        fixture_source.write_text(
            "#define PYTHON_EXECUTABLE " + json.dumps(sys.executable) + "\n"
            + C_FIXTURE
        )
        cls.fixture_binary = cls.build / "fixture-runtime"
        compiled = subprocess.run(
            [compiler, "-O2", "-o", str(cls.fixture_binary), str(fixture_source)],
            text=True, capture_output=True
        )
        if compiled.returncode:
            cls.build_directory.cleanup()
            raise RuntimeError("Cannot compile regression fixture: " + compiled.stderr)
        payload = bytearray(cls.fixture_binary.read_bytes())
        payload[8:11] = b"AI\x02"
        cls.fixture_binary.write_bytes(payload)
        cls.fixture_binary.chmod(0o755)
        cls.extractor = cls.build / "extractor.py"
        cls.extractor.write_text(FIXTURE_PYTHON)
        cls.extractor.chmod(0o644)

    @classmethod
    def tearDownClass(cls):
        cls.build_directory.cleanup()

    def setUp(self):
        self.case_directory = tempfile.TemporaryDirectory(
            prefix="appimage-regression-case-"
        )
        self.addCleanup(self.case_directory.cleanup)
        self.base = Path(self.case_directory.name)
        if os.geteuid() == 0:
            account = pwd.getpwnam("nobody")
            self.uid, self.gid = account.pw_uid, account.pw_gid
        else:
            self.uid, self.gid = os.getuid(), os.getgid()
        self.own(self.base)
        self.home = self.directory("home")
        self.tmp = self.directory("temporary")
        self.work = self.directory("work")
        self.tree = self.directory("fixture-tree")
        self.write_tree("fixture.desktop", DESKTOP)
        self.write_tree("fixture.png", PNG)
        self.write_tree("AppRun", "#!/bin/sh\nexit 0\n")
        self.image = self.make_image("Example App.AppImage")
        self.environment = {
            **os.environ,
            "HOME": str(self.home),
            "XDG_DATA_HOME": str(self.home / ".local/share"),
            "TMPDIR": str(self.tmp),
            "FIXTURE_TREE": str(self.tree),
            "FIXTURE_EXTRACTOR": str(self.extractor),
            "FIXTURE_MODE": "ok",
            "FIXTURE_EXTRACT_MARKER": str(self.base / "extracted.json"),
            "FIXTURE_LAUNCH_OUTPUT": str(self.base / "launched.json"),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        # Keep tests away from a real graphical/session service.
        for key in (
            "DBUS_SESSION_BUS_ADDRESS", "DISPLAY", "WAYLAND_DISPLAY",
            "XDG_RUNTIME_DIR", "SUDO_USER", "SUDO_UID", "SUDO_GID",
            "TARGET_APPIMAGE", "APPIMAGE", "APPDIR", "ARGV0",
            "APPIMAGE_EXTRACT_AND_RUN",
        ):
            self.environment.pop(key, None)

    def own(self, path: Path, executable=False):
        path.chmod(0o755 if path.is_dir() or executable else 0o644)
        if os.geteuid() == 0:
            os.chown(path, self.uid, self.gid)
        return path

    def directory(self, name: str):
        path = self.base / name
        path.mkdir(parents=True, exist_ok=True)
        for parent in (path, *path.parents):
            if parent == self.base:
                break
            self.own(parent)
        return path

    def write_tree(self, name: str, payload: str | bytes):
        path = self.tree / name
        path.parent.mkdir(parents=True, exist_ok=True)
        for parent in (path.parent, *path.parent.parents):
            if parent == self.base:
                break
            self.own(parent)
        if isinstance(payload, str):
            path.write_text(payload, encoding="utf-8")
        else:
            path.write_bytes(payload)
        self.own(path)
        return path

    def make_image(self, name: str):
        path = self.base / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self.fixture_binary, path)
        return self.own(path)

    def demote(self):
        if os.geteuid() == 0:
            os.setgroups([])
            os.setgid(self.gid)
            os.setuid(self.uid)

    def command(self, *options, image=None, yes=True):
        return (
            [BASH, str(SCRIPT)] + (["--yes"] if yes else [])
            + list(options) + [str(self.image if image is None else image)]
        )

    def run_integrator(self, *options, image=None, yes=True, environment=None):
        return subprocess.run(
            self.command(*options, image=image, yes=yes),
            cwd=self.work, env=environment or self.environment,
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
            timeout=20, start_new_session=True, preexec_fn=self.demote,
        )

    def assert_success(self, result):
        self.assertEqual(
            result.returncode, 0,
            "stdout:\n" + result.stdout + "\nstderr:\n" + result.stderr,
        )

    def assert_failure(self, result):
        self.assertNotEqual(
            result.returncode, 0,
            "Unexpected success:\n" + result.stdout + "\n" + result.stderr,
        )

    @property
    def data_home(self):
        return Path(self.environment["XDG_DATA_HOME"])

    def desktop(self, identifier="test"):
        return self.data_home / "applications" / (
            "appimage-" + identifier + ".desktop"
        )

    def entry(self, identifier="test"):
        return desktop_groups(self.desktop(identifier))["Desktop Entry"]

    def assert_temporary_clean(self):
        self.assertEqual(list(self.tmp.iterdir()), [])

    def assert_not_executed(self):
        self.assertFalse(Path(self.environment["FIXTURE_EXTRACT_MARKER"]).exists())
        self.assertFalse(Path(self.environment["FIXTURE_LAUNCH_OUTPUT"]).exists())

    def installed_launchers(self):
        return sorted((self.data_home / "applications").glob("*.desktop"))

    def wait_for_json(self, path: Path, process=None):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                return json.loads(path.read_text())
            except (FileNotFoundError, json.JSONDecodeError):
                if process is not None and process.poll() is not None:
                    stdout, stderr = process.communicate()
                    self.fail(
                        f"Process exited before writing {path.name}:\n"
                        + stdout + stderr
                    )
                time.sleep(0.02)
        self.fail("Fixture did not produce " + path.name)

    def install_tool(self, name: str, body: str):
        tool_dir = self.directory("controlled-tools")
        path = tool_dir / name
        path.write_text("#!/bin/sh\n" + body)
        self.own(path, executable=True)
        self.environment["PATH"] = str(tool_dir) + os.pathsep + os.environ["PATH"]
        return path

    def invoke_with_tty(self, reply: str):
        pid, descriptor = pty.fork()
        if pid == 0:
            try:
                self.demote()
                os.chdir(self.work)
                os.execve(
                    BASH, self.command("--id", "test", yes=False),
                    self.environment,
                )
            except BaseException:
                os._exit(125)
        output = bytearray()
        answered = False
        status = None
        deadline = time.monotonic() + 15
        try:
            while time.monotonic() < deadline:
                ready, _, _ = select.select([descriptor], [], [], 0.05)
                if ready:
                    try:
                        chunk = os.read(descriptor, 65536)
                    except OSError:
                        chunk = b""
                    output.extend(chunk)
                # Accept either conventional y/N capitalization.
                lowered = bytes(output).lower()
                if not answered and (
                    b"[y/n]" in lowered or b"[yes/no]" in lowered
                    or b"trust" in lowered and b"? " in lowered
                ):
                    os.write(descriptor, reply.encode() + b"\n")
                    answered = True
                finished, waited_status = os.waitpid(pid, os.WNOHANG)
                if finished:
                    status = os.waitstatus_to_exitcode(waited_status)
                    break
            if status is None:
                os.killpg(pid, signal.SIGKILL)
                os.waitpid(pid, 0)
                self.fail(
                    "Interactive fixture timed out:\n"
                    + output.decode(errors="replace")
                )
        finally:
            os.close(descriptor)
        self.assertTrue(answered, output.decode(errors="replace"))
        return status, output.decode(errors="replace")

    def launch_with_gio(self, uris=None, action=None):
        output = Path(self.environment["FIXTURE_LAUNCH_OUTPUT"])
        output.unlink(missing_ok=True)
        arguments = (
            ["action", action] if action is not None
            else ["uris", json.dumps(uris or [])]
        )
        result = subprocess.run(
            [sys.executable, "-c", GIO_LAUNCH, str(self.desktop()), *arguments],
            cwd=self.work, env=self.environment, capture_output=True, text=True,
            timeout=10, start_new_session=True, preexec_fn=self.demote,
        )
        self.assert_success(result)
        return self.wait_for_json(output)

    @unittest.skipUnless(os.geteuid() == 0, "Root refusal needs a root test runner.")
    def test_root_execution_refused(self):
        result = subprocess.run(
            self.command("--id", "test"), env=self.environment,
            cwd=self.work, capture_output=True, text=True, timeout=10,
        )
        self.assert_failure(result)
        self.assertIn("root", result.stderr.lower())
        self.assert_not_executed()

    def test_invalid_header_has_no_executable_or_install_side_effects(self):
        self.image.write_text("#!/bin/sh\nexit 99\n")
        result = self.run_integrator("--id", "test")
        self.assert_failure(result)
        self.assertEqual(self.image.stat().st_mode & 0o777, 0o644)
        self.assert_not_executed()
        self.assertEqual(self.installed_launchers(), [])

    def test_type_one_marker_rejected(self):
        payload = bytearray(self.image.read_bytes())
        payload[10] = 1
        self.image.write_bytes(payload)
        result = self.run_integrator("--id", "test")
        self.assert_failure(result)
        self.assert_not_executed()

    def test_missing_or_directory_input_rejected(self):
        for image in (self.base / "missing.AppImage", self.work):
            with self.subTest(image=image):
                self.assert_failure(self.run_integrator("--id", "test", image=image))
        self.assert_not_executed()

    def test_invalid_ids_rejected_before_extraction(self):
        for identifier in ("../bad", "/absolute", "-leading", "has space"):
            with self.subTest(identifier=identifier):
                self.assert_failure(self.run_integrator("--id=" + identifier))
        self.assert_not_executed()

    def test_invalid_names_rejected_before_extraction(self):
        for name in ("", "   ", "bad\nname", "bad\tname", "bad" + chr(27)):
            with self.subTest(name=name):
                self.assert_failure(self.run_integrator("--name", name))
        self.assert_not_executed()

    def test_input_control_character_rejected(self):
        image = self.make_image("newline\nname.AppImage")
        result = self.run_integrator("--id", "test", image=image)
        self.assert_failure(result)
        self.assert_not_executed()
        self.assertEqual(image.stat().st_mode & 0o777, 0o644)

    def test_nonpositive_timeout_rejected_before_extraction(self):
        for timeout in ("0", "-1"):
            with self.subTest(timeout=timeout):
                self.assert_failure(self.run_integrator("--timeout=" + timeout))
        self.assert_not_executed()

    def test_noninteractive_use_requires_explicit_trust(self):
        result = self.run_integrator("--id", "test", yes=False)
        self.assert_failure(result)
        self.assertIn("--yes", result.stderr)
        self.assert_not_executed()
        self.assertEqual(self.image.stat().st_mode & 0o777, 0o644)

    def test_interactive_rejection_leaves_source_and_outputs_untouched(self):
        _, output = self.invoke_with_tty("n")
        self.assert_not_executed()
        self.assertEqual(self.image.stat().st_mode & 0o777, 0o644)
        self.assertEqual(self.installed_launchers(), [])
        self.assertIn("cancel", output.lower())

    def test_interactive_acceptance_installs_launcher(self):
        status, output = self.invoke_with_tty("y")
        self.assertEqual(status, 0, output)
        self.assertTrue(self.desktop().is_file())
        self.assert_temporary_clean()

    def test_basic_installation_preserves_supported_metadata(self):
        result = self.run_integrator("--id", "test")
        self.assert_success(result)
        entry = self.entry()
        self.assertEqual(entry["Name"], "Fixture Editor")
        self.assertEqual(entry["Name[de]"], "Testeditor")
        self.assertEqual(entry["GenericName"], "Editor")
        self.assertEqual(entry["Terminal"], "false")
        self.assertEqual(entry["Categories"], "Utility;")
        self.assertEqual(entry["MimeType"], "text/plain;")
        self.assertEqual(entry["StartupWMClass"], "FixtureEditor")
        self.assertEqual(entry["DBusActivatable"], "false")
        self.assertEqual(desktop_unescape(entry["TryExec"]), str(self.image))
        self.assertNotIn("Path", entry)
        self.assertEqual(entry["X-AppImage-Integrator"], "true")
        self.assertEqual(Path(desktop_unescape(entry["Icon"])).read_bytes(), PNG)
        self.assertEqual(self.image.stat().st_mode & 0o777, 0o744)
        self.assert_temporary_clean()

    def test_relative_path_with_leading_dash(self):
        image = self.work / "-Editor.AppImage"
        shutil.copyfile(self.image, image)
        self.own(image)
        result = self.run_integrator("--id", "test", "--", image="./-Editor.AppImage")
        self.assert_success(result)
        self.assertEqual(desktop_unescape(self.entry()["TryExec"]), str(image))

    def test_missing_desktop_creates_generic_launcher_without_url_assumption(self):
        (self.tree / "fixture.desktop").unlink()
        self.assert_success(self.run_integrator("--id", "test"))
        entry = self.entry()
        self.assertEqual(entry["Name"], "Example App")
        self.assertNotIn("%U", entry["Exec"])
        self.assertNotIn("Actions", entry)
        self.assertNotIn("MimeType", entry)

    def test_missing_icon_uses_theme_fallback(self):
        (self.tree / "fixture.png").unlink()
        self.assert_success(self.run_integrator("--id", "test"))
        self.assertEqual(self.entry()["Icon"], "application-x-executable")

    def test_multiple_desktops_need_explicit_selection(self):
        self.write_tree(
            "second.desktop", DESKTOP.replace("Fixture Editor", "Selected Editor")
        )
        result = self.run_integrator("--id", "test")
        self.assert_failure(result)
        self.assertEqual(self.installed_launchers(), [])
        self.assert_temporary_clean()
        result = self.run_integrator("--id", "test", "--desktop", "second.desktop")
        self.assert_success(result)
        self.assertEqual(self.entry()["Name"], "Selected Editor")

    def test_explicit_nested_desktop_selection(self):
        (self.tree / "fixture.desktop").unlink()
        self.write_tree("nested/application.desktop", DESKTOP)
        result = self.run_integrator(
            "--id", "test", "--desktop", "nested/application.desktop"
        )
        self.assert_success(result)
        self.assertEqual(self.entry()["Name"], "Fixture Editor")

    def test_desktop_selection_cannot_escape_appdir(self):
        for selection in ("../outside.desktop", "/outside.desktop"):
            with self.subTest(selection=selection):
                result = self.run_integrator("--id", "test", "--desktop", selection)
                self.assert_failure(result)
                self.assertEqual(self.installed_launchers(), [])
                self.assert_temporary_clean()

    def test_internal_symlinks_and_standard_metadata_fallback(self):
        desktop = self.write_tree("usr/share/applications/fixture.desktop", DESKTOP)
        icon = self.write_tree("usr/share/icons/hicolor/32x32/apps/fixture.png", PNG)
        (self.tree / "fixture.desktop").unlink()
        (self.tree / "fixture.png").unlink()
        (self.tree / "fixture.desktop").symlink_to(
            desktop.relative_to(self.tree)
        )
        (self.tree / ".DirIcon").symlink_to(icon.relative_to(self.tree))
        self.assert_success(self.run_integrator("--id", "test"))
        self.assertEqual(self.entry()["Name"], "Fixture Editor")
        self.assertEqual(Path(desktop_unescape(self.entry()["Icon"])).read_bytes(), PNG)
        (self.tree / "fixture.desktop").unlink()
        self.assert_success(self.run_integrator("--id", "test"))
        self.assertEqual(self.entry()["Name"], "Fixture Editor")

    def test_external_desktop_symlink_is_not_read(self):
        outside = self.base / "outside.desktop"
        outside.write_text(DESKTOP.replace("Fixture Editor", "OUTSIDE SECRET"))
        (self.tree / "fixture.desktop").unlink()
        (self.tree / "fixture.desktop").symlink_to(outside)
        result = self.run_integrator("--id", "test")
        self.assert_success(result)
        self.assertNotIn("OUTSIDE SECRET", self.desktop().read_text())
        self.assertEqual(self.entry()["Name"], "Example App")

    def test_external_icon_symlink_is_not_copied(self):
        outside = self.base / "outside.png"
        outside.write_bytes(PNG)
        (self.tree / "fixture.png").unlink()
        (self.tree / "fixture.png").symlink_to(outside)
        (self.tree / ".DirIcon").symlink_to(outside)
        self.assert_success(self.run_integrator("--id", "test"))
        self.assertEqual(self.entry()["Icon"], "application-x-executable")

    def test_external_metadata_directory_symlink_is_not_traversed(self):
        external = self.directory("outside-applications")
        (external / "external.desktop").write_text(
            DESKTOP.replace("Fixture Editor", "OUTSIDE DIRECTORY")
        )
        (self.tree / "fixture.desktop").unlink()
        self.write_tree("usr/share/placeholder", "")
        (self.tree / "usr/share/applications").symlink_to(external)
        self.assert_success(self.run_integrator("--id", "test"))
        self.assertNotIn("OUTSIDE DIRECTORY", self.desktop().read_text())

    def test_extensionless_diricon_content_formats(self):
        (self.tree / "fixture.png").unlink()
        for content, suffix in ((PNG, ".png"), (SVG, ".svg"), (XPM, ".xpm")):
            with self.subTest(suffix=suffix):
                self.write_tree(".DirIcon", content)
                self.assert_success(self.run_integrator("--id", "test"))
                icon = Path(desktop_unescape(self.entry()["Icon"]))
                self.assertEqual(icon.suffix, suffix)
                self.assertEqual(icon.read_bytes(), content)

    def test_oversized_icon_falls_back(self):
        self.write_tree("fixture.png", PNG + bytes(16 * 1024 * 1024))
        self.assert_success(self.run_integrator("--id", "test"))
        self.assertEqual(self.entry()["Icon"], "application-x-executable")

    def test_extraction_failure_preserves_existing_caller_directory(self):
        caller_tree = self.work / "squashfs-root"
        caller_tree.mkdir()
        sentinel = caller_tree / "keep.txt"
        sentinel.write_text("original content")
        self.environment["FIXTURE_MODE"] = "fail"
        result = self.run_integrator("--id", "test")
        self.assert_failure(result)
        self.assertIn("23", result.stderr)
        self.assertIn("controlled extraction failure", result.stderr)
        self.assertEqual(sentinel.read_text(), "original content")
        self.assertEqual(self.installed_launchers(), [])
        self.assert_temporary_clean()

    def test_success_preserves_existing_caller_directory(self):
        caller_tree = self.work / "squashfs-root"
        caller_tree.mkdir()
        sentinel = caller_tree / "keep.txt"
        sentinel.write_text("original content")
        self.assert_success(self.run_integrator("--id", "test"))
        self.assertEqual(sentinel.read_text(), "original content")
        self.assert_temporary_clean()

    def test_missing_or_symlink_extraction_root_is_rejected(self):
        for mode in ("missing", "symlink-root"):
            with self.subTest(mode=mode):
                self.environment["FIXTURE_MODE"] = mode
                result = self.run_integrator("--id", "test")
                self.assert_failure(result)
                self.assertEqual(self.installed_launchers(), [])
                self.assert_temporary_clean()

    def test_timeout_kills_extractor_and_cleans_temporary_files(self):
        self.environment["FIXTURE_MODE"] = "sleep"
        result = self.run_integrator("--id", "test", "--timeout", "1")
        self.assert_failure(result)
        self.assertTrue(
            "timeout" in result.stderr.lower() or "timed out" in result.stderr.lower(),
            result.stderr,
        )
        marker = self.wait_for_json(Path(self.environment["FIXTURE_EXTRACT_MARKER"]))
        with self.assertRaises(ProcessLookupError):
            os.kill(marker["pid"], 0)
        self.assert_temporary_clean()
        self.assertEqual(self.installed_launchers(), [])

    def test_sigterm_kills_extractor_before_cleaning_temporary_files(self):
        self.environment["FIXTURE_MODE"] = "sleep"
        process = subprocess.Popen(
            self.command("--id", "test"), cwd=self.work, env=self.environment,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, start_new_session=True,
            preexec_fn=self.demote,
        )
        try:
            marker = self.wait_for_json(
                Path(self.environment["FIXTURE_EXTRACT_MARKER"]), process
            )
            process.send_signal(signal.SIGTERM)
            stdout, stderr = process.communicate(timeout=8)
            self.assertNotEqual(process.returncode, 0, stdout + stderr)
            with self.assertRaises(ProcessLookupError):
                os.kill(marker["pid"], 0)
            self.assert_temporary_clean()
            self.assertEqual(self.installed_launchers(), [])
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            if process.stdout:
                process.stdout.close()
            if process.stderr:
                process.stderr.close()

    def test_ambiguous_or_invalid_desktop_structure_fails(self):
        variants = (
            DESKTOP.replace("Name=Fixture Editor", "Name=First\nName=Second"),
            DESKTOP + "\n[Desktop Entry]\nName=Duplicate\n",
            "[Desktop Entry]\nthis is not a key\n",
        )
        for text in variants:
            with self.subTest(text=text[:60]):
                self.write_tree("fixture.desktop", text)
                self.assert_failure(self.run_integrator("--id", "test"))
                self.assertEqual(self.installed_launchers(), [])
                self.assert_temporary_clean()

    def test_invalid_utf8_desktop_is_rejected(self):
        self.write_tree("fixture.desktop", b"[Desktop Entry]\nName=\xff\n")
        self.assert_failure(self.run_integrator("--id", "test"))
        self.assertEqual(self.installed_launchers(), [])
        self.assert_temporary_clean()

    def test_oversized_desktop_is_rejected(self):
        self.write_tree(
            "fixture.desktop", DESKTOP + "\n#" + "x" * (1024 * 1024)
        )
        self.assert_failure(self.run_integrator("--id", "test"))
        self.assertEqual(self.installed_launchers(), [])
        self.assert_temporary_clean()

    def test_known_wrappers_need_explicit_simple_exec(self):
        for command in (
            "env TEST=value fixture %U",
            'sh -c "fixture"',
            "python3 script.py",
        ):
            with self.subTest(command=command):
                self.write_tree(
                    "fixture.desktop",
                    DESKTOP.replace("Exec=fixture --flag %U", "Exec=" + command),
                )
                result = self.run_integrator("--id", "test")
                self.assert_failure(result)
                self.assertIn("--simple-exec", result.stderr)
                self.assertEqual(self.installed_launchers(), [])
                self.assert_temporary_clean()

    def test_simple_exec_discards_arguments_actions_and_mime_types(self):
        self.write_tree(
            "fixture.desktop",
            DESKTOP.replace("Exec=fixture --flag %U", 'Exec=sh -c "fixture"'),
        )
        self.assert_success(self.run_integrator("--id", "test", "--simple-exec"))
        groups = desktop_groups(self.desktop())
        entry = groups["Desktop Entry"]
        self.assertEqual(entry["Name"], "Fixture Editor")
        self.assertEqual(entry["Name[de]"], "Testeditor")
        self.assertNotIn("--flag", entry["Exec"])
        self.assertNotIn("%U", entry["Exec"])
        self.assertNotIn("Actions", entry)
        self.assertNotIn("MimeType", entry)
        self.assertEqual(list(groups), ["Desktop Entry"])

    def test_simple_exec_still_rejects_malformed_desktop_structure(self):
        self.write_tree(
            "fixture.desktop",
            DESKTOP.replace("Name=Fixture Editor", "Name=First\nName=Duplicate"),
        )
        self.assert_failure(self.run_integrator("--id", "test", "--simple-exec"))
        self.assertEqual(self.installed_launchers(), [])

    def test_supported_actions_preserve_individual_arguments(self):
        self.assert_success(self.run_integrator("--id", "test"))
        groups = desktop_groups(self.desktop())
        self.assertEqual(groups["Desktop Entry"]["Actions"], "New;")
        self.assertIn("--new-window %U", groups["Desktop Action New"]["Exec"])
        self.assertNotIn("Desktop Action Other", groups)

    def test_action_original_executable_must_match_exactly(self):
        changed = DESKTOP.replace(
            "Exec=fixture --flag %U", "Exec=/opt/native/fixture --flag %U"
        ).replace(
            "Exec=fixture --new-window %U", "Exec=/elsewhere/fixture --new-window %U"
        )
        self.write_tree("fixture.desktop", changed)
        result = self.run_integrator("--id", "test")
        self.assert_success(result)
        groups = desktop_groups(self.desktop())
        self.assertNotIn("Actions", groups["Desktop Entry"])
        self.assertNotIn("Desktop Action New", groups)

    def test_malformed_action_is_omitted_without_corrupting_main_command(self):
        self.write_tree(
            "fixture.desktop",
            DESKTOP.replace("Exec=fixture --new-window %U", "Exec=fixture %x"),
        )
        self.assert_success(self.run_integrator("--id", "test"))
        entry = self.entry()
        self.assertIn("--flag %U", entry["Exec"])
        self.assertNotIn("Actions", entry)

    def test_unsupported_main_exec_syntax_is_rejected(self):
        for command in (
            "fixture %x", "fixture %U %F", 'fixture "%U"',
            "fixture --files=%F", "fixture --icon=%i",
            'fixture --arg="partial quoting"',
        ):
            with self.subTest(command=command):
                self.write_tree(
                    "fixture.desktop",
                    DESKTOP.replace("Exec=fixture --flag %U", "Exec=" + command),
                )
                self.assert_failure(self.run_integrator("--id", "test"))
                self.assertEqual(self.installed_launchers(), [])
                self.assert_temporary_clean()

    def test_visibility_and_unrecognized_vendor_bindings_are_omitted(self):
        self.write_tree(
            "fixture.desktop",
            DESKTOP.replace(
                "DBusActivatable=true",
                "DBusActivatable=true\nHidden=true\nNoDisplay=true\n"
                "OnlyShowIn=GNOME;\nX-Vendor-Run=/native/helper",
            ) + "\n[Vendor Launch]\nExec=unrelated-command\n",
        )
        result = self.run_integrator("--id", "test")
        self.assert_success(result)
        groups = desktop_groups(self.desktop())
        entry = groups["Desktop Entry"]
        for key in ("Hidden", "NoDisplay", "OnlyShowIn", "X-Vendor-Run", "Path"):
            self.assertNotIn(key, entry)
        self.assertNotIn("Vendor Launch", groups)
        self.assertIn("Hidden", result.stderr)

    def test_name_override_removes_old_localized_names(self):
        result = self.run_integrator("--id", "test", "--name", "My Own Editor")
        self.assert_success(result)
        entry = self.entry()
        self.assertEqual(entry["Name"], "My Own Editor")
        self.assertNotIn("Name[de]", entry)

    def test_custom_absolute_xdg_data_home(self):
        self.environment["XDG_DATA_HOME"] = str(self.directory("custom data é"))
        self.assert_success(self.run_integrator("--id", "test"))
        self.assertTrue(self.desktop().is_file())
        icon = Path(desktop_unescape(self.entry()["Icon"]))
        self.assertTrue(icon.is_relative_to(self.data_home))
        self.assertFalse((self.home / ".local/share/applications").exists())

    def test_relative_xdg_data_home_uses_standard_fallback(self):
        environment = {**self.environment, "XDG_DATA_HOME": "relative-data"}
        result = self.run_integrator("--id", "test", environment=environment)
        self.assert_success(result)
        self.assertTrue(self.desktop().exists())
        self.assertFalse((self.work / "relative-data").exists())
        self.assertIn("relative", result.stderr.lower())

    def test_repeating_same_id_updates_one_launcher(self):
        self.assert_success(self.run_integrator("--id", "test"))
        first_icon = self.entry()["Icon"]
        self.assert_success(self.run_integrator("--id", "test"))
        self.assertEqual(self.entry()["Icon"], first_icon)
        updated = self.make_image("Editor 2.0.AppImage")
        self.assert_success(self.run_integrator("--id", "test", image=updated))
        self.assertEqual(desktop_unescape(self.entry()["TryExec"]), str(updated))
        self.assertEqual(len(self.installed_launchers()), 1)

    def test_changed_icon_and_launcher_are_committed_together_on_success(self):
        self.assert_success(self.run_integrator("--id", "test"))
        old_icon = Path(desktop_unescape(self.entry()["Icon"]))
        (self.tree / "fixture.png").unlink()
        self.write_tree("fixture.svg", SVG)
        self.assert_success(self.run_integrator("--id", "test"))
        new_icon = Path(desktop_unescape(self.entry()["Icon"]))
        self.assertNotEqual(old_icon, new_icon)
        self.assertEqual(new_icon.read_bytes(), SVG)
        self.assertFalse(old_icon.exists())

    def test_input_symlink_is_resolved_and_default_identity_is_stable(self):
        alias = self.base / "Stable.AppImage"
        alias.symlink_to(self.image.name)
        self.assert_success(self.run_integrator(image=alias))
        first = self.installed_launchers()
        self.assertEqual(len(first), 1)
        entry = desktop_groups(first[0])["Desktop Entry"]
        self.assertEqual(desktop_unescape(entry["TryExec"]), str(self.image))
        expected = hashlib.sha256(os.fsencode(str(self.image))).hexdigest()[:20]
        self.assertEqual(first[0].name, "appimage-" + expected + ".desktop")
        self.assert_success(self.run_integrator())
        self.assertEqual(self.installed_launchers(), first)
        updated = self.make_image("Different.AppImage")
        alias.unlink()
        alias.symlink_to(updated.name)
        # A launcher already installed via the alias still references the old target.
        self.assertEqual(
            desktop_unescape(desktop_groups(first[0])["Desktop Entry"]["TryExec"]),
            str(self.image),
        )

    def test_runtime_redirection_environment_is_cleared_for_extraction(self):
        variables = (
            "TARGET_APPIMAGE", "APPIMAGE", "APPDIR", "ARGV0",
            "APPIMAGE_EXTRACT_AND_RUN",
        )
        environment = {**self.environment, **{key: "redirect-value" for key in variables}}
        self.assert_success(
            self.run_integrator("--id", "test", environment=environment)
        )
        marker = self.wait_for_json(Path(self.environment["FIXTURE_EXTRACT_MARKER"]))
        self.assertEqual(marker["runtime_environment"], {key: None for key in variables})

    def test_unmanaged_launcher_is_not_overwritten(self):
        self.directory("home/.local/share/applications")
        original = b"[Desktop Entry]\nType=Application\nName=Keep me\nExec=/bin/true\n"
        self.desktop().write_bytes(original)
        self.own(self.desktop())
        self.assert_failure(self.run_integrator("--id", "test"))
        self.assertEqual(self.desktop().read_bytes(), original)
        self.assert_temporary_clean()

    def test_destination_launcher_symlink_is_not_followed(self):
        self.directory("home/.local/share/applications")
        target = self.base / "unrelated.txt"
        target.write_text("untouched")
        self.desktop().symlink_to(target)
        self.assert_failure(self.run_integrator("--id", "test"))
        self.assertTrue(self.desktop().is_symlink())
        self.assertEqual(target.read_text(), "untouched")
        self.assert_temporary_clean()

    def test_destination_asset_directory_symlink_is_refused(self):
        self.directory("home/.local/share/appimage-integrator")
        outside = self.directory("unrelated-icons")
        sentinel = outside / "keep.txt"
        sentinel.write_text("untouched")
        (self.data_home / "appimage-integrator/icons").symlink_to(outside)
        self.assert_failure(self.run_integrator("--id", "test"))
        self.assertEqual(list(outside.iterdir()), [sentinel])
        self.assertFalse(self.desktop().exists())
        self.assert_temporary_clean()

    def test_destination_lock_symlink_is_refused(self):
        self.directory("home/.local/share/appimage-integrator")
        target = self.base / "lock-target"
        target.write_text("untouched")
        (self.data_home / "appimage-integrator/.lock").symlink_to(target)
        self.assert_failure(self.run_integrator("--id", "test"))
        self.assertEqual(target.read_text(), "untouched")
        self.assertFalse(self.desktop().exists())
        self.assert_temporary_clean()

    def test_nonregular_lock_file_is_refused_without_blocking(self):
        self.directory("home/.local/share/appimage-integrator")
        lock = self.data_home / "appimage-integrator/.lock"
        os.mkfifo(lock, 0o600)
        if os.geteuid() == 0:
            os.chown(lock, self.uid, self.gid)
        result = self.run_integrator("--id", "test")
        self.assert_failure(result)
        self.assertTrue(lock.is_fifo())
        self.assertFalse(self.desktop().exists())
        self.assert_temporary_clean()

    def test_failed_validator_preserves_previous_launcher_and_icon(self):
        self.assert_success(self.run_integrator("--id", "test"))
        previous = self.desktop().read_bytes()
        icon = Path(desktop_unescape(self.entry()["Icon"]))
        icon_bytes = icon.read_bytes()
        self.install_tool(
            "desktop-file-validate",
            'printf "%s\\n" "controlled validation failure" >&2\nexit 1\n',
        )
        self.write_tree("fixture.png", PNG + b"new icon bytes")
        result = self.run_integrator("--id", "test", "--name", "Changed")
        self.assert_failure(result)
        self.assertIn("controlled validation failure", result.stderr)
        self.assertEqual(self.desktop().read_bytes(), previous)
        self.assertEqual(icon.read_bytes(), icon_bytes)
        self.assert_temporary_clean()

    def test_failed_desktop_cache_refresh_warns_after_successful_install(self):
        self.install_tool(
            "update-desktop-database",
            'printf "%s\\n" "controlled cache failure" >&2\nexit 1\n',
        )
        result = self.run_integrator("--id", "test")
        self.assert_success(result)
        self.assertTrue(self.desktop().exists())
        self.assertIn("cache", result.stderr.lower())

    def test_optional_desktop_helpers_can_be_absent(self):
        isolated_path = self.directory("minimal-path")
        (isolated_path / "python3").symlink_to(sys.executable)
        (isolated_path / "bash").symlink_to(BASH)
        environment = {**self.environment, "PATH": str(isolated_path)}
        result = self.run_integrator("--id", "test", environment=environment)
        self.assert_success(result)
        self.assertTrue(self.desktop().exists())
        self.assertIn("desktop-file-validate", result.stderr)
        self.assertIn("update-desktop-database", result.stderr)

    @unittest.skipUnless(GIO_AVAILABLE, "libgio-2.0 is unavailable.")
    def test_gio_delivers_preserved_arguments_and_uri(self):
        self.assert_success(self.run_integrator("--id", "test"))
        launched = self.launch_with_gio(["https://example.test/a%20b"])
        self.assertEqual(launched["image"], str(self.image))
        self.assertEqual(
            launched["arguments"], ["--flag", "https://example.test/a%20b"]
        )

    @unittest.skipUnless(GIO_AVAILABLE, "libgio-2.0 is unavailable.")
    def test_gio_launches_special_paths_without_evaluating_filename(self):
        cases = (
            "Space File.AppImage",
            "Unicode é and العربية.AppImage",
            "single' double\" slash\\ dollar$ back" + chr(96) + ".AppImage",
            "percent%U and 50%.AppImage",
            "contains=equals.AppImage",
            "combined=%U.AppImage",
            "literal$(touch SHOULD_NOT_EXIST)" + chr(96) + "touch ALSO_NOT" + chr(96) + ".AppImage",
        )
        for filename in cases:
            with self.subTest(filename=filename):
                image = self.make_image(filename)
                self.assert_success(
                    self.run_integrator("--id", "test", image=image)
                )
                launched = self.launch_with_gio(["https://example.test/item"])
                self.assertEqual(launched["image"], str(image))
                self.assertEqual(
                    launched["arguments"],
                    ["--flag", "https://example.test/item"],
                )
                self.assertFalse((self.work / "SHOULD_NOT_EXIST").exists())
                self.assertFalse((self.work / "ALSO_NOT").exists())
        self.assert_temporary_clean()

    @unittest.skipUnless(GIO_AVAILABLE, "libgio-2.0 is unavailable.")
    def test_gio_preserves_quoted_arguments_literal_percent_and_local_files(self):
        self.write_tree(
            "fixture.desktop",
            DESKTOP.replace(
                "Exec=fixture --flag %U",
                'Exec=fixture "argument with spaces" --ratio=100%% %F',
            ),
        )
        local_file = self.base / "Document with spaces.txt"
        local_file.write_text("test")
        self.assert_success(self.run_integrator("--id", "test"))
        launched = self.launch_with_gio([local_file.as_uri()])
        self.assertEqual(
            launched["arguments"],
            ["argument with spaces", "--ratio=100%", str(local_file)],
        )

    @unittest.skipUnless(GIO_AVAILABLE, "libgio-2.0 is unavailable.")
    def test_gio_desktop_action_runs_its_own_arguments(self):
        self.assert_success(self.run_integrator("--id", "test"))
        launched = self.launch_with_gio(action="New")
        self.assertEqual(launched["image"], str(self.image))
        self.assertEqual(launched["arguments"], ["--new-window"])


if __name__ == "__main__":
    if not BASH:
        raise SystemExit("Bash is required to run this test suite.")
    if not SCRIPT.is_file():
        raise SystemExit("Integrator script not found: " + str(SCRIPT))
    unittest.main(verbosity=2)
