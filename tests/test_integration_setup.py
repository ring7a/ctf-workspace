"""Meaningful project configuration preservation tests; no WSL/model calls."""
import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import tomllib
import unittest
import subprocess
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('workspace_integration_setup', SOURCE / 'tools/integrations/setup.py')
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)

class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='integration-config-')
        self.root = Path(self.tmp.name)
        self.old_root = setup.ROOT
        setup.ROOT = self.root.resolve()
        (self.root / '.integrations/rea/work/logs').mkdir(parents=True)
        self.report = b'{"healthy":true,"scope":{"mode":"explicit"}}\n'
        (self.root / '.integrations/rea/work/logs/doctor.json').write_bytes(self.report)
        self.state = {'schema_version': 1, 'rea': {'package': 'rea-agents', 'version': '6.4.0'},
                      'doctor': {'provider': 'ghidra', 'healthy': True, 'scope_mode': 'explicit',
                                 'report_sha256': hashlib.sha256(self.report).hexdigest()}}
        (self.root / '.integrations/rea/install-state.json').write_text(json.dumps(self.state), encoding='utf-8')

    def tearDown(self):
        setup.ROOT = self.old_root
        self.tmp.cleanup()

    def register(self):
        with patch.object(setup, 'wsl_path', return_value="/mnt/e/student's workspace/tools/rea.sh"):
            setup.register_rea()

    def test_preserves_unrelated_servers_and_settings(self):
        (self.root / '.mcp.json').write_text(json.dumps({'mcpServers': {'existing': {'url': 'https://example.invalid/mcp'}}}), encoding='utf-8')
        (self.root / '.codex').mkdir()
        original = '# owner comment\nmodel = "configured-model"\n[mcp_servers.existing]\nurl = "https://example.invalid/mcp"\n'
        (self.root / '.codex/config.toml').write_text(original, encoding='utf-8')
        self.register()
        claude = json.loads((self.root / '.mcp.json').read_text())
        codex_text = (self.root / '.codex/config.toml').read_text()
        codex = tomllib.loads(codex_text)
        self.assertEqual(claude['mcpServers']['existing']['url'], 'https://example.invalid/mcp')
        self.assertEqual(codex['model'], 'configured-model')
        self.assertIn('# owner comment', codex_text)
        self.assertEqual(codex['mcp_servers']['rea']['tool_timeout_sec'], 420)
        self.assertEqual(claude['mcpServers']['rea']['args'][-2:], ["/mnt/e/student's workspace/tools/rea.sh", 'mcp'])

    def test_idempotent_and_keeps_first_backup(self):
        original = '{"mcpServers": {}}\n'
        (self.root / '.mcp.json').write_text(original, encoding='utf-8')
        self.register()
        content = (self.root / '.mcp.json').read_bytes()
        self.register()
        self.assertEqual((self.root / '.mcp.json').read_bytes(), content)
        self.assertEqual((self.root / '.mcp.json.pre-integrations.backup').read_text(), original)

    def test_conflict_does_not_partially_write_claude(self):
        (self.root / '.codex').mkdir()
        (self.root / '.codex/config.toml').write_text('[mcp_servers.rea]\ncommand="other"\n', encoding='utf-8')
        with self.assertRaisesRegex(RuntimeError, 'differs'):
            self.register()
        self.assertFalse((self.root / '.mcp.json').exists())

    def test_malformed_codex_does_not_write_claude(self):
        (self.root / '.codex').mkdir()
        (self.root / '.codex/config.toml').write_text('not = [valid', encoding='utf-8')
        with self.assertRaises(tomllib.TOMLDecodeError):
            self.register()
        self.assertFalse((self.root / '.mcp.json').exists())

    def test_missing_runtime_defers_registration(self):
        (self.root / '.integrations/rea/install-state.json').unlink()
        with self.assertRaisesRegex(RuntimeError, 'deferred'):
            self.register()
        self.assertFalse((self.root / '.mcp.json').exists())

    def test_rejects_workspace_escape(self):
        with self.assertRaisesRegex(ValueError, 'escapes'):
            setup.write_managed(self.root.parent / 'outside-integration.json', '{}')

    def test_stale_or_malformed_state_defers_registration(self):
        for state in ({}, {**self.state, 'rea': []}, {**self.state, 'doctor': None},
                      {**self.state, 'rea': {'package': 'rea-agents', 'version': 'wrong'}}):
            with self.subTest(state=state):
                (self.root / '.integrations/rea/install-state.json').write_text(json.dumps(state), encoding='utf-8')
                with self.assertRaisesRegex(RuntimeError, 'deferred'):
                    self.register()
                self.assertFalse((self.root / '.mcp.json').exists())

    def test_changed_or_unhealthy_doctor_defers_registration(self):
        for report in (b'{"healthy":false,"scope":{"mode":"explicit"}}', self.report + b' '):
            with self.subTest(report=report):
                (self.root / '.integrations/rea/work/logs/doctor.json').write_bytes(report)
                with self.assertRaisesRegex(RuntimeError, 'deferred'):
                    self.register()
                self.assertFalse((self.root / '.mcp.json').exists())

    @unittest.skipUnless(setup.os.name == 'nt', 'Windows setup entry point')
    def test_install_failure_prevents_registration(self):
        results = [subprocess.CompletedProcess([], code) for code in (0, 2)]
        with patch.object(setup.sys, 'argv', ['setup.py']), \
                patch.object(setup, 'wsl_path', return_value='/mnt/c/fixture/tools/integrations/install-rea.sh'), \
                patch.object(setup, 'register_rea') as register, \
                patch.object(setup, 'run', side_effect=results) as runner:
            with self.assertRaisesRegex(RuntimeError, 'REA exited 2'):
                setup.main()
        self.assertEqual(runner.call_count, 2)
        register.assert_not_called()

    @unittest.skipUnless(setup.os.name == 'nt', 'Windows setup entry point')
    def test_default_and_all_install_only_rea(self):
        for arguments in (['setup.py'], ['setup.py', '--component', 'all']):
            with self.subTest(arguments=arguments), \
                    patch.object(setup.sys, 'argv', arguments), \
                    patch.object(setup, 'wsl_path', return_value='/mnt/c/fixture/tools/integrations/install-rea.sh'), \
                    patch.object(setup, 'register_rea') as register, \
                    patch.object(setup, 'run', return_value=subprocess.CompletedProcess([], 0)) as runner:
                self.assertEqual(setup.main(), 0)
                self.assertEqual(runner.call_count, 2)
                self.assertTrue(runner.call_args.args[0][-1].endswith('/install-rea.sh'))
                register.assert_called_once_with()

    def test_removed_component_is_rejected_before_calls(self):
        with patch.object(setup.sys, 'argv', ['setup.py', '--component', 'ctf-agent']), \
                patch.object(setup, 'run') as runner, \
                patch.object(setup, 'register_rea') as register:
            with self.assertRaises(SystemExit) as caught:
                setup.main()
        self.assertEqual(caught.exception.code, 2)
        runner.assert_not_called()
        register.assert_not_called()

if __name__ == '__main__':
    unittest.main()
