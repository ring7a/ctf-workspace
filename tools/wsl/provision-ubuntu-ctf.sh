#!/usr/bin/env bash
# Provision a freshly-imported ubuntu-ctf WSL distro for CTF use.
# Run as ROOT inside the distro (setup-ubuntu-ctf.ps1 does this).
# Idempotent. Reproduces the WORKING 2026-10-09 setup.
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
# REPO = the repo root as seen from inside WSL (setup-ubuntu-ctf.ps1 passes it).
REPO="${REPO:?set REPO to the repo root inside WSL, e.g. /mnt/e/path/to/ctf}"
INSTALLER="${INSTALLER:-$REPO/tools/vendor-ctf-skills/scripts/install_ctf_tools.sh}"
REQS="${REQS:-$REPO/tools/wsl/ctf-venv-requirements.txt}"
VENV="/home/$CTF_USER/.ctf-tools/venv"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root (the .ps1 wrapper does: wsl -d ubuntu-ctf -u root bash provision.sh)" >&2
  exit 1
fi

echo "== 1) user '$CTF_USER' with passwordless sudo + default-user wsl.conf =="
id "$CTF_USER" 2>/dev/null || useradd -m -s /bin/bash "$CTF_USER"
usermod -aG sudo "$CTF_USER"
echo "$CTF_USER ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/$CTF_USER"
chmod 440 "/etc/sudoers.d/$CTF_USER"
echo "$CTF_USER:$CTF_USER" | chpasswd
printf '[user]\ndefault=%s\n[boot]\nsystemd=false\n[network]\ngenerateResolvConf=true\n' \
  "$CTF_USER" > /etc/wsl.conf
command -v sudo >/dev/null || { apt-get update -q; apt-get install -y -q sudo; }

sudo -u "$CTF_USER" -H INSTALLER="$INSTALLER" REQS="$REQS" VENV="$VENV" bash -s <<'USERPART'
set -euo pipefail

echo "== 2) apt build deps + system CTF tools =="
sudo DEBIAN_FRONTEND=noninteractive apt-get update -q
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q \
  python3-venv python3-pip python3-dev python3-full build-essential \
  libgmp-dev libmpfr-dev libmpc-dev libffi-dev libssl-dev pkg-config curl
# System analysis tools (gdb, binwalk, steghide, exiftool, nmap, ...) via the
# vendored installer's apt mode (CRLF-stripped first).
cp "$INSTALLER" ~/install_ctf_tools.sh
sed -i 's/\r$//' ~/install_ctf_tools.sh
chmod +x ~/install_ctf_tools.sh
bash ~/install_ctf_tools.sh apt || echo "WARN: apt mode had failures (see ~/.ctf-tools/*.log)"

echo "== 3) uv + Python 3.12 venv =="
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv python install 3.12
rm -rf "$VENV"
uv venv --python 3.12 "$VENV"

echo "== 4) install the exact frozen CTF package set =="
export VIRTUAL_ENV="$VENV"
if [ -f "$REQS" ]; then
  sed 's/\r$//' "$REQS" > /tmp/ctf-reqs.txt
  uv pip install -r /tmp/ctf-reqs.txt
else
  echo "WARN: $REQS missing; falling back to installer python-mode specs"
  SPECS=$(sed -n '/PIP_PACKAGES=(/,/^)/p' ~/install_ctf_tools.sh \
          | grep -oE '"[^"]+"' | tr -d '"' | sed 's/:.*//' | grep '==')
  for s in $SPECS; do n=${s%%==*}; uv pip install "$s" || uv pip install "$n" || echo "FAIL $n"; done
  uv pip install 'pycparser==2.22' cysignals
fi

echo "== 5) auto-activate the CTF venv in interactive shells =="
LINE='[ -f ~/.ctf-tools/venv/bin/activate ] && source ~/.ctf-tools/venv/bin/activate'
grep -qF "$LINE" ~/.bashrc || echo "$LINE" >> ~/.bashrc

echo "== provision: python tool check =="
source "$VENV/bin/activate"
for m in pwn angr fpylll volatility3 unicorn capstone; do
  python -c "import $m" 2>/dev/null && echo "OK $m" || echo "FAIL $m"
done
USERPART

echo "provision complete; run 'wsl --terminate ubuntu-ctf' to apply wsl.conf"
