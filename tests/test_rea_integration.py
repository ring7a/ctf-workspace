"""Local launcher safety checks. Run in WSL: python3 -I tests/test_rea_integration.py.

The tests use authored fake executables, never downloads or challenge binaries.
Real provider validation is recorded separately in .integrations/rea/work/NOTES.md.
"""
import os
import hashlib
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "posix" and Path("/bin/bash").exists(), "Run launcher tests in WSL")
class ReaLauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="ctf-rea-test-")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.repo = self.base / "student's workspace"
        (self.repo / "tools/integrations").mkdir(parents=True)
        shutil.copyfile(SOURCE / "tools/rea.sh", self.repo / "tools/rea.sh")
        shutil.copyfile(SOURCE / "tools/integrations/install-rea.sh", self.repo / "tools/integrations/install-rea.sh")
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.fake(self.bin / "uname", 'if [[ "$1" == -s ]]; then echo Linux; else echo x86_64; fi\n')
        self.fake(self.bin / "grep", "exit 0\n")
        self.env = {**os.environ, "PATH": f"{self.bin}:/usr/bin:/bin", "WSL_DISTRO_NAME": "ubuntu-ctf"}
        for key in ("GHIDRA_INSTALL_DIR", "JAVA_HOME", "REA_ANALYSIS_PROVIDER", "REA_GHIDRA_STARTUP_TIMEOUT_MS", "GHIDRA_HEADLESS_MAXMEM"):
            self.env.pop(key, None)
        self.workspace_base = self.repo / ".integrations/rea"
        (self.workspace_base / "work").mkdir(parents=True)
        root = self.repo.resolve().as_posix()
        self.project_key = hashlib.sha256(root.encode()).hexdigest()[:16]
        self.native_parent = Path.home() / ".ctf-integrations/rea"
        self.native_base = self.native_parent / self.project_key
        # Do not touch a pre-existing project prefix or follow a linked ancestor.
        for ancestor in (Path.home() / ".ctf-integrations", self.native_parent, self.native_base):
            if ancestor.is_symlink():
                raise RuntimeError(f"Fixture native prefix has a linked ancestor: {ancestor}")
        if self.native_base.exists():
            raise RuntimeError(f"Preserving pre-existing native prefix: {self.native_base}")
        self.native_base.mkdir(parents=True)
        self.owner_nonce = secrets.token_hex(16)
        self.owner_marker = self.native_base / ".rea-test-owner"
        self.owner_marker.write_text(self.owner_nonce, encoding="utf-8")
        self.addCleanup(self.cleanup_native_prefix)
        self.runtime = self.native_base / "work/runtime"
        self.entry = self.runtime / "app/node_modules/rea-agents/scripts/rea.mjs"
        self.entry.parent.mkdir(parents=True)
        self.entry.write_text("// authored fixture\n", encoding="utf-8")
        node = self.runtime / "node/bin/node"
        node.parent.mkdir(parents=True)
        self.fake(node, 'printf "%s\\n" "$PWD" "$GHIDRA_INSTALL_DIR" "$JAVA_HOME" "$REA_ANALYSIS_PROVIDER" "$REA_GHIDRA_STARTUP_TIMEOUT_MS" "$GHIDRA_HEADLESS_MAXMEM" "$@"\n')

    def cleanup_native_prefix(self):
        """Remove only this fixture's hash prefix; never follow a replaced link."""
        expected = self.native_parent / self.project_key
        if self.native_base != expected or self.native_base.parent != self.native_parent:
            raise RuntimeError("Refusing fixture cleanup outside the owned native prefix")
        for ancestor in (Path.home() / ".ctf-integrations", self.native_parent):
            if ancestor.is_symlink():
                raise RuntimeError("Refusing cleanup through a replaced native ancestor")
        if self.native_base.is_symlink():
            # The native-prefix escape test owns this link, not its destination.
            self.native_base.unlink()
        elif self.native_base.exists():
            if self.owner_marker.is_symlink() or not self.owner_marker.is_file() or self.owner_marker.read_text(encoding="utf-8") != self.owner_nonce:
                raise RuntimeError("Preserving native prefix without matching fixture ownership")
            shutil.rmtree(self.native_base)

    def fake(self, path, body):
        path.write_text("#!/bin/bash\n" + body, encoding="utf-8")
        path.chmod(0o755)

    def run_tool(self, relative, *args):
        return subprocess.run(["/bin/bash", str(self.repo / relative), *args], cwd=self.base,
                              env=self.env, text=True, capture_output=True, timeout=10)

    def test_literal_arguments_and_working_directory(self):
        args = ("search", "file with spaces", "$(touch NOPE); `touch ALSO_NOPE`", "--json")
        result = self.run_tool("tools/rea.sh", *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = result.stdout.splitlines()
        self.assertEqual(lines[0], str(self.repo / ".integrations/rea/work"))
        self.assertEqual(lines[6:], [str(self.entry), *args])
        self.assertFalse((self.base / "NOPE").exists())
        self.assertFalse((self.repo / ".integrations/rea/work/NOPE").exists())

    def test_defaults_are_native_ghidra_and_pinned_paths(self):
        result = self.run_tool("tools/rea.sh", "mcp")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[1:6], [
            str(self.runtime / "ghidra/ghidra_12.1.4_PUBLIC"), str(self.runtime / "jdk"), "ghidra", "330000", "2G"])
        self.assertEqual(result.stdout.splitlines()[-1], "mcp")

    def test_explicit_provider_environment_is_preserved(self):
        self.env.update(GHIDRA_INSTALL_DIR="/opt/own ghidra", JAVA_HOME="/opt/own jdk",
                        REA_ANALYSIS_PROVIDER="ghidra", REA_GHIDRA_STARTUP_TIMEOUT_MS="600000",
                        GHIDRA_HEADLESS_MAXMEM="512M")
        result = self.run_tool("tools/rea.sh", "doctor")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[1:6], ["/opt/own ghidra", "/opt/own jdk", "ghidra", "600000", "512M"])

    def test_other_distribution_is_rejected(self):
        self.env["WSL_DISTRO_NAME"] = "Ubuntu"
        result = self.run_tool("tools/rea.sh", "mcp")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ubuntu-ctf", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_symlink_parent_cannot_escape_workspace(self):
        shutil.rmtree(self.repo / ".integrations")
        outside = self.base / "outside"
        outside.mkdir()
        (self.repo / ".integrations").symlink_to(outside, target_is_directory=True)
        result = self.run_tool("tools/rea.sh", "mcp")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("symlink", result.stderr)
        self.assertEqual(list(outside.iterdir()), [])

    def test_symlink_executable_cannot_escape_runtime(self):
        node = self.runtime / "node/bin/node"
        node.unlink()
        outside = self.bin / "external-node"
        self.fake(outside, "echo SHOULD_NOT_RUN\n")
        node.symlink_to(outside)
        result = self.run_tool("tools/rea.sh", "mcp")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("escapes", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_native_prefix_symlink_cannot_escape_runtime(self):
        self.cleanup_native_prefix()
        outside = self.base / "outside-native"
        outside.mkdir()
        sentinel = outside / "preserved-user-file"
        sentinel.write_text("preserve this unrelated content", encoding="utf-8")
        self.native_base.symlink_to(outside, target_is_directory=True)
        result = self.run_tool("tools/rea.sh", "mcp")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("symlink", result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve this unrelated content")

    def test_missing_runtime_explains_install_command(self):
        shutil.rmtree(self.runtime)
        result = self.run_tool("tools/rea.sh", "mcp")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("install-rea.sh", result.stderr)

    def test_installer_rejects_unknown_options_before_network(self):
        for args in (("--destination", "/tmp/elsewhere"), ("--arbitrary-command",), ("--check", "extra")):
            with self.subTest(args=args):
                result = self.run_tool("tools/integrations/install-rea.sh", *args)
                self.assertEqual(result.returncode, 2)
        self.assertFalse((self.repo / ".integrations/rea/untrusted").exists())

    def test_installer_help_needs_no_runtime(self):
        result = self.run_tool("tools/integrations/install-rea.sh", "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--check", result.stdout)


if __name__ == "__main__":
    unittest.main()
