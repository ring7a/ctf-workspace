"""Install REA in ubuntu-ctf and register project MCP only.

This is trusted orchestration, not a challenge interpreter. Run with Python -I.
No secrets are copied, global agent configuration is not modified.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[2]

def wsl_path(path: Path) -> str:
    text = str(path.resolve()).replace('\\', '/')
    if len(text) < 3 or text[1:3] != ':/':
        raise ValueError('Use this setup entry point from Windows with a local drive workspace.')
    return '/mnt/' + text[0].lower() + text[2:]

def plain_path(path: Path) -> None:
    if not path.resolve().is_relative_to(ROOT):
        raise ValueError(f'Path escapes workspace: {path}')
    current = path
    while current != ROOT:
        if current.is_symlink() or (current.exists() and getattr(current.stat(follow_symlinks=False), 'st_file_attributes', 0) & 0x400):
            raise ValueError(f'Refusing linked/reparse path: {current}')
        current = current.parent

def run(args: list[str], timeout: int) -> subprocess.CompletedProcess:
    child = subprocess.Popen(args, cwd=ROOT, text=True, encoding='utf-8', errors='replace',
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    try:
        code = child.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        # Kill only this orchestrator's owned client tree, never WSL VM/services.
        if os.name == 'nt':
            subprocess.run(['taskkill.exe', '/PID', str(child.pid), '/T', '/F'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            child.kill()
        child.wait(timeout=10)
        raise RuntimeError('WSL client did not respond before its deadline. No distribution/service was stopped.')
    return subprocess.CompletedProcess(args, code)

def write_managed(path: Path, content: str) -> None:
    plain_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = path.read_text(encoding='utf-8') if path.exists() else None
    if previous == content:
        return
    if previous is not None:
        backup = path.with_name(path.name + '.pre-integrations.backup')
        plain_path(backup)
        if not backup.exists():
            backup.write_text(previous, encoding='utf-8', newline='\n')
    tmp = path.with_name(path.name + '.integration-tmp')
    plain_path(tmp)
    with tmp.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(content)
    os.replace(tmp, path)

def register_rea() -> None:
    state = ROOT / '.integrations/rea/install-state.json'
    plain_path(state)
    if not state.is_file():
        raise RuntimeError('REA installation has not passed its scoped doctor; registration is deferred.')
    installed = json.loads(state.read_text(encoding='utf-8'))
    report_path = ROOT / '.integrations/rea/work/logs/doctor.json'
    plain_path(report_path)
    if (not isinstance(installed, dict) or installed.get('schema_version') != 1
            or not isinstance(installed.get('rea'), dict)
            or not isinstance(installed.get('doctor'), dict)
            or installed.get('rea', {}).get('version') != '6.4.0'
            or installed.get('rea', {}).get('package') != 'rea-agents'
            or installed.get('doctor', {}).get('provider') != 'ghidra'
            or installed.get('doctor', {}).get('healthy') is not True
            or installed.get('doctor', {}).get('scope_mode') != 'explicit'
            or not report_path.is_file()):
        raise RuntimeError('REA installation state is incomplete or differs from the reviewed version; registration is deferred.')
    report_bytes = report_path.read_bytes()
    report = json.loads(report_bytes)
    if (hashlib.sha256(report_bytes).hexdigest() != installed['doctor'].get('report_sha256')
            or not isinstance(report, dict) or report.get('healthy') is not True
            or not isinstance(report.get('scope'), dict) or report['scope'].get('mode') != 'explicit'):
        raise RuntimeError('REA scoped doctor evidence is missing, changed or unhealthy; registration is deferred.')
    args = ['-d', 'ubuntu-ctf', '--', 'bash', '--noprofile', '--norc', wsl_path(ROOT / 'tools/rea.sh'), 'mcp']
    server = {'command': 'wsl.exe', 'args': args}
    claude_path = ROOT / '.mcp.json'
    plain_path(claude_path)
    claude = json.loads(claude_path.read_text(encoding='utf-8')) if claude_path.exists() else {'mcpServers': {}}
    if not isinstance(claude, dict) or not isinstance(claude.get('mcpServers', {}), dict):
        raise RuntimeError('Existing project MCP JSON is invalid; refusing to replace it.')
    existing = claude.setdefault('mcpServers', {}).get('rea')
    if existing is not None and existing != server:
        raise RuntimeError('Existing project rea registration differs; inspect it before replacement.')
    claude['mcpServers']['rea'] = server
    codex_path = ROOT / '.codex/config.toml'
    plain_path(codex_path)
    codex_text = codex_path.read_text(encoding='utf-8') if codex_path.exists() else ''
    parsed = tomllib.loads(codex_text)
    expected = {**server, 'startup_timeout_sec': 90, 'tool_timeout_sec': 420}
    current = parsed.get('mcp_servers', {}).get('rea')
    if current is not None and current != expected:
        raise RuntimeError('Existing project Codex rea registration differs; inspect it before replacement.')
    if current is None:
        codex_text = codex_text.rstrip() + '\n\n[mcp_servers.rea]\ncommand = "wsl.exe"\nargs = ' + json.dumps(args) + '\nstartup_timeout_sec = 90\ntool_timeout_sec = 420\n'
    # All formats and existing registrations were checked before either write.
    write_managed(claude_path, json.dumps(claude, ensure_ascii=False, indent=2) + '\n')
    write_managed(codex_path, codex_text.lstrip())
    print('REA registered in project .mcp.json and .codex/config.toml. Reopen Claude/Codex to discover tools.', flush=True)

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--component', choices=['all', 'rea'], default='rea',
                        help='Install REA only; all remains a compatibility alias for rea.')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--check', action='store_true')
    modes.add_argument('--register-only', action='store_true')
    args = parser.parse_args()
    if os.name != 'nt' or not sys.flags.isolated:
        parser.error('Use Windows Python -I; actual installation and target handling run in ubuntu-ctf.')
    if args.register_only:
        register_rea()
        return 0
    # A short own-client probe prevents hanging indefinitely on broken WSL.
    print('Checking ubuntu-ctf availability...', flush=True)
    result = run(['wsl.exe', '-d', 'ubuntu-ctf', '--', '/usr/bin/true'], 20)
    if result.returncode:
        raise RuntimeError('ubuntu-ctf availability check failed.')
    print(f'{"Checking" if args.check else "Installing"} REA in its separate local runtime...', flush=True)
    command = ['wsl.exe', '-d', 'ubuntu-ctf', '--', 'bash', '--noprofile', '--norc',
               wsl_path(ROOT / 'tools/integrations/install-rea.sh')]
    if args.check:
        command.append('--check')
    result = run(command, 120 if args.check else 3600)
    if result.returncode:
        raise RuntimeError(f'REA exited {result.returncode}; no completion is claimed.')
    if not args.check:
        register_rea()
    print('REA integration steps completed.', flush=True)
    return 0

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(f'Integration setup: {error}', file=sys.stderr)
        raise SystemExit(1)
