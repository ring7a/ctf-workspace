#!/usr/bin/env bash
# Provision a freshly-imported ubuntu-ctf WSL distro for CTF use.
# Run as ROOT inside the distro (setup-ubuntu-ctf.ps1 does this).
# Run only in a dedicated distro. Keeps an existing Python 3.12 venv.
#
# Why this shape: Ubuntu 26.04 ships Python 3.14, and several pinned CTF
# packages (numpy 2.2.6, unicorn, lief) have no cp314 wheels while angr's
# pyvex fails to build on 3.14. So Python packages go into a dedicated
# Python 3.12 venv created with `uv`, installed from a frozen requirements
# file that already includes the two fixes found during bring-up:
#   - pycparser==2.22  (newer pycparser breaks `import angr`)
#   - cysignals        (required by fpylll at import time)
set -euo pipefail

CTF_USER="${CTF_USER:-ctf}"
[[ "$CTF_USER" =~ ^[a-z_][a-z0-9_-]*$ ]] || { echo "Invalid CTF_USER" >&2; exit 2; }
INSTALL_DOCKER="${INSTALL_DOCKER:-1}"
[[ "$INSTALL_DOCKER" == 0 || "$INSTALL_DOCKER" == 1 ]] || { echo "INSTALL_DOCKER must be 0 or 1" >&2; exit 2; }
# REPO = the repo root as seen from inside WSL (setup-ubuntu-ctf.ps1 passes it).
REPO="${REPO:?set REPO to the repo root inside WSL, e.g. /mnt/e/path/to/ctf}"
INSTALLER="${INSTALLER:-$REPO/tools/vendor-ctf-skills/scripts/install_ctf_tools.sh}"
REQS="${REQS:-$REPO/tools/wsl/ctf-venv-requirements.txt}"
VENV="/home/$CTF_USER/.ctf-tools/venv"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root (the .ps1 wrapper does: wsl -d ubuntu-ctf -u root bash provision.sh)" >&2
  exit 1
fi
[ -f "$INSTALLER" ] && [ -f "$REQS" ] || { echo "Missing installer or frozen requirements" >&2; exit 1; }

export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q sudo ca-certificates curl tmux

echo "== 1) user '$CTF_USER' with passwordless sudo + default-user wsl.conf =="
id "$CTF_USER" 2>/dev/null || useradd -m -s /bin/bash "$CTF_USER"
usermod -aG sudo "$CTF_USER"
echo "$CTF_USER ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/$CTF_USER"
chmod 440 "/etc/sudoers.d/$CTF_USER"
printf '[user]\ndefault=%s\n[boot]\nsystemd=true\n[network]\ngenerateResolvConf=true\n' \
  "$CTF_USER" > /etc/wsl.conf
if [ "$INSTALL_DOCKER" == 1 ]; then
  apt-get install -y -q docker.io docker-compose-v2
  usermod -aG docker "$CTF_USER"
  systemctl enable docker
fi

sudo -u "$CTF_USER" -H INSTALLER="$INSTALLER" REQS="$REQS" VENV="$VENV" bash -s <<'USERPART'
set -euo pipefail

echo "== 2) apt build deps + system CTF tools =="
sudo DEBIAN_FRONTEND=noninteractive apt-get update -q
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q \
  python3-venv python3-pip python3-dev python3-full build-essential \
  libgmp-dev libmpfr-dev libmpc-dev libffi-dev libssl-dev pkg-config curl gdb-multiarch
# System analysis tools (gdb, binwalk, steghide, exiftool, nmap, ...) via the
# vendored installer's apt mode (CRLF-stripped first).
cp "$INSTALLER" ~/install_ctf_tools.sh
sed -i 's/\r$//' ~/install_ctf_tools.sh
chmod +x ~/install_ctf_tools.sh
# Some optional distro packages may be unavailable; preserve the vendor's log.
bash ~/install_ctf_tools.sh apt || echo "WARN: optional apt tools failed (see ~/.ctf-tools/*.log)"

echo "== 3) uv + Python 3.12 venv =="
export PATH="$HOME/.local/bin:$PATH"
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.12
if [ -e "$VENV" ] || [ -L "$VENV" ]; then
  [ ! -L "$VENV" ] && [ -x "$VENV/bin/python" ] || { echo "Refusing invalid venv: $VENV" >&2; exit 1; }
  "$VENV/bin/python" -I -c 'import sys; sys.exit(sys.version_info[:2] != (3, 12))' || { echo "Existing venv must use Python 3.12" >&2; exit 1; }
else
  uv venv --python 3.12 "$VENV"
fi

echo "== 4) install the exact frozen CTF package set =="
export VIRTUAL_ENV="$VENV"
REQ_TMP="$(mktemp)"
trap 'rm -f -- "$REQ_TMP"' EXIT
sed 's/\r$//' "$REQS" > "$REQ_TMP"
uv pip install -r "$REQ_TMP"
uv pip check

echo "== 4b) vendor hlextend (working hash length-extension; hashpumpy==1.2 is broken on py3.12) =="
HLX_SP="$("$VENV/bin/python" -I -c 'import site;print(site.getsitepackages()[0])')"
curl -fsSL -o "$HLX_SP/hlextend.py" https://raw.githubusercontent.com/stephenbradshaw/hlextend/master/hlextend.py && echo "  hlextend -> $HLX_SP/hlextend.py" || echo "  WARN: hlextend download failed; add manually"

echo "== 5) auto-activate the CTF venv for ALL login shells =="
# /etc/profile.d runs for login shells including non-interactive `bash -lc`,
# which is how the agents invoke tools (`wsl -d ubuntu-ctf -u ctf -e bash -lc`).
# A ~/.bashrc line is NOT enough — non-interactive bash skips .bashrc.
sudo tee /etc/profile.d/ctf-venv.sh >/dev/null <<SH
if [ -f "$VENV/bin/activate" ]; then
  . "$VENV/bin/activate"
fi
SH
sudo chmod 644 /etc/profile.d/ctf-venv.sh

echo "== provision: python tool check =="
source "$VENV/bin/activate"
failures=0
for m in pwn angr fpylll volatility3 unicorn capstone; do
  if python -I -c "import $m"; then
    echo "OK $m"
  else
    echo "FAIL $m" >&2
    failures=$((failures + 1))
  fi
done
[ "$failures" -eq 0 ] || exit 1
USERPART

echo "provision complete; run 'wsl --terminate ubuntu-ctf' to apply wsl.conf"
