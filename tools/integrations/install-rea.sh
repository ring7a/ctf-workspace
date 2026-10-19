#!/usr/bin/env bash
# Workspace-local REA/Ghidra/Node/JDK installer. Run only in WSL ubuntu-ctf.
# Downloads stay in untrusted; unpacking and all third-party execution stay in work.
set -euo pipefail
umask 077

REA_VERSION=6.4.0
REA_RELEASE_COMMIT=a56f7bb668ab23fec8d33f7af353ac7ed2fe1895
NODE_VERSION=24.15.0
NODE_SHA256=472655581fb851559730c48763e0c9d3bc25975c59d518003fc0849d3e4ba0f6
JDK_VERSION=21.0.11+10
JDK_ARCHIVE=OpenJDK21U-jdk_x64_linux_hotspot_21.0.11_10.tar.gz
JDK_SHA256=4b2220e232a97997b436ca6ab15cbf70171ecff52958a46159dfa5a8c44ca4de
GHIDRA_VERSION=12.1.4
GHIDRA_ARCHIVE=ghidra_12.1.4_PUBLIC_20260921.zip
GHIDRA_SHA256=ddac49f903da9d5bac833e5cc79395098b9c33cfd3279be5f31bd00387d2d4db

fail() { printf '%s\n' "REA installer: $*" >&2; exit 1; }
usage() { printf '%s\n' 'Usage: bash tools/integrations/install-rea.sh [--check | --help]'; }
MODE=install
if [[ $# -gt 0 ]]; then
  [[ $# -eq 1 ]] || { usage >&2; exit 2; }
  case "$1" in --check) MODE=check ;; --help|-h) usage; exit 0 ;; *) usage >&2; exit 2 ;; esac
fi
[[ "$(uname -s)" == Linux ]] || fail 'Run inside WSL ubuntu-ctf.'
grep -qi microsoft /proc/sys/kernel/osrelease || fail 'Run inside WSL ubuntu-ctf.'
[[ "${WSL_DISTRO_NAME:-}" == ubuntu-ctf ]] || fail 'Use the isolated ubuntu-ctf distribution.'
[[ "$(uname -m)" == x86_64 ]] || fail 'These pinned native assets require Linux x64.'
for tool in curl tar unzip sha256sum python3 realpath flock timeout stat; do
  command -v "$tool" >/dev/null || fail "Missing prerequisite: $tool"
done
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)"
BASE="$ROOT/.integrations/rea"
WORK="$BASE/work"
DOWNLOADS="$BASE/untrusted"
PROJECT_KEY="$(printf '%s' "$ROOT" | sha256sum | cut -c1-16)"
NATIVE_BASE="$HOME/.ctf-integrations/rea/$PROJECT_KEY"
RUNTIME="$NATIVE_BASE/work/runtime"
case "$(stat -f -c %T "$HOME")" in 9p|drvfs) fail 'The Linux home must support native Unix symlinks; use the default ubuntu-ctf home.' ;; esac
for dir in "$ROOT/.integrations" "$BASE" "$WORK" "$DOWNLOADS" "$WORK/logs" "$DOWNLOADS/npm-cache" \
  "$HOME/.ctf-integrations" "$HOME/.ctf-integrations/rea" "$NATIVE_BASE" "$NATIVE_BASE/work" "$RUNTIME"; do
  [[ ! -L "$dir" ]] || fail "Refusing symlink directory: $dir"
done
if [[ "$MODE" == check ]]; then
  [[ -f "$BASE/install-state.json" && ! -L "$BASE/install-state.json" ]] || fail 'No completed REA installation.'
  cd -- "$WORK"
  bash --noprofile --norc "$ROOT/tools/rea.sh" doctor --provider ghidra --json | python3 -I -c '
import json, sys
report = json.load(sys.stdin)
if not isinstance(report, dict) or report.get("healthy") is not True or not isinstance(report.get("scope"), dict) or report["scope"].get("mode") != "explicit":
    raise SystemExit("REA scoped Ghidra doctor is not healthy")
print(json.dumps(report))
'
  exit 0
fi
mkdir -p -- "$DOWNLOADS" "$RUNTIME" "$WORK/logs" "$DOWNLOADS/npm-cache"
[[ "$(realpath -- "$BASE")" == "$BASE" ]] || fail 'Installation path escapes the workspace.'
[[ "$(realpath -- "$NATIVE_BASE")" == "$NATIVE_BASE" ]] || fail 'Native runtime path escapes its dedicated prefix.'
[[ ! -L "$WORK/install.lock" ]] || fail 'Refusing symlink install lock.'
exec 9>"$WORK/install.lock"
flock -n 9 || fail 'Another REA installation is running.'
cd -- "$WORK"

fetch() {
  local url="$1" destination="$2"
  [[ "$url" == https://* && ! -L "$destination" && ! -L "$destination.part" ]] || fail 'Invalid download destination.'
  if [[ ! -f "$destination" ]]; then
    curl --fail --location --proto '=https' --proto-redir '=https' --retry 3 \
      --connect-timeout 30 --max-time 1800 --output "$destination.part" "$url"
    mv -- "$destination.part" "$destination"
  fi
}
verify_sha() {
  local file="$1" expected="$2"
  [[ "$expected" =~ ^[0-9a-f]{64}$ ]] || fail 'Invalid pinned SHA-256.'
  printf '%s  %s\n' "$expected" "$file" | sha256sum --check --status || fail "Checksum failed: $file"
}
# Refuse archive traversal, absolute entries, links outside their top directory,
# devices, and duplicate normalized names before invoking tar/unzip.
check_archive() {
  python3 -I - "$1" <<'PY'
import pathlib, sys, tarfile, zipfile
path = pathlib.Path(sys.argv[1])
seen = set()
def check(name, link=None):
    p = pathlib.PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or not p.parts:
        raise SystemExit('Unsafe archive path: ' + name)
    normalized = str(p)
    if normalized in seen:
        raise SystemExit('Duplicate archive path: ' + name)
    seen.add(normalized)
    if link is not None:
        q = pathlib.PurePosixPath(link)
        if q.is_absolute():
            raise SystemExit('Absolute archive link: ' + name)
        parts = list(p.parent.parts)
        for part in q.parts:
            if part == '..':
                if len(parts) <= 1:
                    raise SystemExit('Escaping archive link: ' + name)
                parts.pop()
            elif part != '.':
                parts.append(part)
if zipfile.is_zipfile(path):
    with zipfile.ZipFile(path) as archive:
        for entry in archive.infolist():
            if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                raise SystemExit('ZIP links are not admitted')
            check(entry.filename)
else:
    with tarfile.open(path) as archive:
        for entry in archive:
            if not (entry.isfile() or entry.isdir() or entry.issym()):
                raise SystemExit('Unsupported archive entry: ' + entry.name)
            check(entry.name, entry.linkname if entry.issym() else None)
PY
}

NODE_ARCHIVE="node-v$NODE_VERSION-linux-x64.tar.xz"
NODE_URL="https://nodejs.org/download/release/v$NODE_VERSION/$NODE_ARCHIVE"
JDK_URL="https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.11%2B10/$JDK_ARCHIVE"
GHIDRA_URL="https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_${GHIDRA_VERSION}_build/$GHIDRA_ARCHIVE"
for dir in "$RUNTIME/node" "$RUNTIME/jdk" "$RUNTIME/ghidra" "$RUNTIME/app" "$DOWNLOADS/npm-cache" "$WORK/logs"; do
  [[ ! -L "$dir" ]] || fail "Refusing symlink directory: $dir"
done
printf 'Installing REA %s; Node %s; Temurin JDK %s; Ghidra %s\n' "$REA_VERSION" "$NODE_VERSION" "$JDK_VERSION" "$GHIDRA_VERSION"
fetch "$NODE_URL" "$DOWNLOADS/$NODE_ARCHIVE"
verify_sha "$DOWNLOADS/$NODE_ARCHIVE" "$NODE_SHA256"
if [[ ! -x "$RUNTIME/node/bin/node" ]]; then
  [[ ! -e "$RUNTIME/node" ]] || fail 'Incomplete node directory; inspect it before retrying.'
  check_archive "$DOWNLOADS/$NODE_ARCHIVE"
  mkdir -- "$RUNTIME/node"
  tar -xJf "$DOWNLOADS/$NODE_ARCHIVE" --strip-components=1 -C "$RUNTIME/node"
fi
export PATH="$RUNTIME/node/bin:$PATH"
[[ "$(node --version)" == "v$NODE_VERSION" ]] || fail 'Unexpected local Node version.'

fetch "$JDK_URL" "$DOWNLOADS/$JDK_ARCHIVE"
verify_sha "$DOWNLOADS/$JDK_ARCHIVE" "$JDK_SHA256"
if [[ ! -x "$RUNTIME/jdk/bin/javac" ]]; then
  [[ ! -e "$RUNTIME/jdk" ]] || fail 'Incomplete JDK directory; inspect it before retrying.'
  check_archive "$DOWNLOADS/$JDK_ARCHIVE"
  mkdir -- "$RUNTIME/jdk"
  tar -xzf "$DOWNLOADS/$JDK_ARCHIVE" --strip-components=1 -C "$RUNTIME/jdk"
fi
fetch "$GHIDRA_URL" "$DOWNLOADS/$GHIDRA_ARCHIVE"
verify_sha "$DOWNLOADS/$GHIDRA_ARCHIVE" "$GHIDRA_SHA256"
if [[ ! -f "$RUNTIME/ghidra/ghidra_${GHIDRA_VERSION}_PUBLIC/support/analyzeHeadless" ]]; then
  [[ ! -e "$RUNTIME/ghidra" ]] || fail 'Incomplete Ghidra directory; inspect it before retrying.'
  check_archive "$DOWNLOADS/$GHIDRA_ARCHIVE"
  mkdir -- "$RUNTIME/ghidra"
  unzip -q "$DOWNLOADS/$GHIDRA_ARCHIVE" -d "$RUNTIME/ghidra"
fi

METADATA="$DOWNLOADS/rea-agents-$REA_VERSION.registry.json"
fetch "https://registry.npmjs.org/rea-agents/$REA_VERSION" "$METADATA"
python3 -I - "$METADATA" "$REA_VERSION" <<'PY'
import json, sys
metadata = json.load(open(sys.argv[1]))
assert metadata['name'] == 'rea-agents' and metadata['version'] == sys.argv[2]
assert metadata['dist']['tarball'] == f'https://registry.npmjs.org/rea-agents/-/rea-agents-{sys.argv[2]}.tgz'
assert metadata['dist']['integrity'].startswith('sha512-')
PY
REA_TARBALL="$DOWNLOADS/rea-agents-$REA_VERSION.tgz"
fetch "https://registry.npmjs.org/rea-agents/-/rea-agents-$REA_VERSION.tgz" "$REA_TARBALL"
python3 -I - "$METADATA" "$REA_TARBALL" <<'PY'
import base64, hashlib, json, pathlib, sys
metadata = json.load(open(sys.argv[1]))
actual = 'sha512-' + base64.b64encode(hashlib.sha512(pathlib.Path(sys.argv[2]).read_bytes()).digest()).decode()
assert actual == metadata['dist']['integrity'], 'Published REA integrity mismatch'
PY
check_archive "$REA_TARBALL"
mkdir -p -- "$RUNTIME/app"
for file in "$RUNTIME/app/package.json" "$RUNTIME/app/package-lock.json" "$WORK/logs/npm-install.log" "$WORK/logs/doctor.json"; do
  [[ ! -L "$file" ]] || fail "Refusing symlink file: $file"
done
for file in "$WORK/npm-user.config" "$WORK/npm-global.config"; do
  [[ ! -L "$file" && (! -e "$file" || ! -s "$file") ]] || fail "Managed empty npm configuration differs: $file"
  touch -- "$file"
done
export NPM_CONFIG_CACHE="$DOWNLOADS/npm-cache" NPM_CONFIG_USERCONFIG="$WORK/npm-user.config"
export NPM_CONFIG_GLOBALCONFIG="$WORK/npm-global.config" HUSKY=0
export NPM_CONFIG_REGISTRY=https://registry.npmjs.org
# The published package already contains dist/ and the Java bridge; no arbitrary
# dependency lifecycle scripts or agent setup/config mutations are needed.
if [[ ! -f "$RUNTIME/app/node_modules/rea-agents/dist/main.js" ]]; then
  timeout --signal=TERM --kill-after=30s 1800s npm --prefix "$RUNTIME/app" install --save-exact --omit=dev --ignore-scripts \
    --no-audit --no-fund "$REA_TARBALL" >"$WORK/logs/npm-install.log" 2>&1 || {
      printf 'npm install failed; see %s\n' "$WORK/logs/npm-install.log" >&2; exit 1;
    }
fi
python3 -I - "$RUNTIME/app/node_modules/rea-agents/package.json" "$REA_VERSION" <<'PY'
import json, sys
metadata = json.load(open(sys.argv[1]))
assert metadata['name'] == 'rea-agents' and metadata['version'] == sys.argv[2], 'Unexpected installed REA version'
PY
export JAVA_HOME="$RUNTIME/jdk" GHIDRA_INSTALL_DIR="$RUNTIME/ghidra/ghidra_${GHIDRA_VERSION}_PUBLIC"
export REA_ANALYSIS_PROVIDER=ghidra
timeout --signal=TERM --kill-after=10s 30s bash --noprofile --norc "$ROOT/tools/rea.sh" --version
timeout --signal=TERM --kill-after=10s 120s bash --noprofile --norc "$ROOT/tools/rea.sh" doctor --provider ghidra --json >"$WORK/logs/doctor.json"
python3 -I - "$BASE" "$METADATA" "$NODE_VERSION" "$NODE_SHA256" "$JDK_VERSION" "$JDK_SHA256" "$GHIDRA_VERSION" "$GHIDRA_SHA256" "$REA_RELEASE_COMMIT" "$RUNTIME" <<'PY'
import datetime, hashlib, json, pathlib, sys
base = pathlib.Path(sys.argv[1])
runtime = pathlib.Path(sys.argv[10])
metadata = json.load(open(sys.argv[2]))
doctor_path = base/'work/logs/doctor.json'
doctor_bytes = doctor_path.read_bytes()
doctor = json.loads(doctor_bytes)
if not isinstance(doctor, dict) or doctor.get('healthy') is not True or not isinstance(doctor.get('scope'), dict) or doctor['scope'].get('mode') != 'explicit':
    raise SystemExit('REA scoped Ghidra doctor is not healthy; installation is incomplete')
state = {
    'schema_version': 1, 'installed_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'rea': {'package': metadata['name'], 'version': metadata['version'], 'release_source_commit': sys.argv[9],
            'npm_git_head': metadata.get('gitHead'),
            'tarball': metadata['dist']['tarball'], 'integrity': metadata['dist']['integrity'],
            'sha256': hashlib.sha256((base/'untrusted'/f"rea-agents-{metadata['version']}.tgz").read_bytes()).hexdigest(),
            'license': metadata.get('license'), 'engines': metadata.get('engines')},
    'node': {'version': sys.argv[3], 'sha256': sys.argv[4]},
    'jdk': {'vendor': 'Eclipse Temurin', 'version': sys.argv[5], 'sha256': sys.argv[6]},
    'ghidra': {'version': sys.argv[7], 'sha256': sys.argv[8]},
    'dependency_lock_sha256': hashlib.sha256((runtime/'app/package-lock.json').read_bytes()).hexdigest(),
    'runtime': str(runtime),
    'storage_policy': 'native ubuntu-ctf home runtime; workspace download cache, logs and state',
    'ghidra_install_dir': str(runtime/'ghidra'/f'ghidra_{sys.argv[7]}_PUBLIC'),
    'java_home': str(runtime/'jdk'),
    'doctor': {'provider': 'ghidra', 'healthy': True, 'scope_mode': 'explicit',
               'report_sha256': hashlib.sha256(doctor_bytes).hexdigest()},
    'install_policy': 'local-published-package; npm lifecycle scripts disabled; no paid providers',
}
destination = base/'install-state.json'
if destination.is_symlink():
    raise SystemExit('Refusing symlink install-state.json')
staging = base/'install-state.json.part'
if staging.is_symlink():
    raise SystemExit('Refusing symlink install-state.json.part')
staging.write_text(json.dumps(state, indent=2) + '\n')
staging.replace(destination)
PY
printf 'REA installation complete. Lock: %s\n' "$BASE/install-state.json"
printf 'CLI: bash %s/tools/rea.sh --help\nMCP: bash %s/tools/rea.sh mcp\n' "$ROOT" "$ROOT"
