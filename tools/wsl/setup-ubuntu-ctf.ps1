# Create and provision a dedicated "ubuntu-ctf" WSL2 distro for CTF work.
# Reproduces the 2026-10-09 setup. Does NOT touch the existing "hrc-rocky" distro
# or change the default distro.
#
# Prereq: WSL2 engine present (`wsl --version` works). On this machine the engine
# was already installed; only a distro was missing.
#
# Usage:  pwsh -File tools\wsl\setup-ubuntu-ctf.ps1
#         (optionally -Tarball <path to an Ubuntu rootfs install.tar.gz>)
param(
  [string]$Distro     = "ubuntu-ctf",
  [string]$InstallDir = "$env:USERPROFILE\WSL\ubuntu-ctf",
  [string]$Tarball    = ""
)
$ErrorActionPreference = "Stop"

# 1) Locate an Ubuntu rootfs tarball. Default: reuse the installed Ubuntu appx's
#    install.tar.gz (no download). Override with -Tarball to pin a version.
if (-not $Tarball) {
  $appx = (Get-AppxPackage *Ubuntu*).InstallLocation | Select-Object -First 1
  if (-not $appx) { throw "No Ubuntu appx found. Run: wsl --install -d Ubuntu --no-launch (or pass -Tarball)" }
  $Tarball = Join-Path $appx "install.tar.gz"
}
if (-not (Test-Path $Tarball)) { throw "Rootfs tarball not found: $Tarball" }
Write-Host "Using rootfs: $Tarball"

# 2) Import as a new distro (registers as root; no interactive user prompt).
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Write-Host "Importing $Distro -> $InstallDir ..."
wsl --import $Distro $InstallDir $Tarball

# 3) Copy the provisioning script into the distro, normalize line endings, run as root.
$prov = Join-Path $PSScriptRoot "provision-ubuntu-ctf.sh"
if (-not (Test-Path $prov)) { throw "Missing $prov" }
# Make the script readable from inside WSL via /mnt and run it.
$winPath = (Resolve-Path $prov).Path
$wslPath = "/mnt/" + ($winPath -replace '^([A-Za-z]):','$1' -replace '\\','/')
$wslPath = $wslPath.Substring(0,5).ToLower() + $wslPath.Substring(5)  # drive letter lowercase
Write-Host "Provisioning (this installs CTF tools; takes a while)..."
wsl -d $Distro -u root bash -c "sed 's/\r`$//' '$wslPath' > /root/provision.sh; INSTALLER='/mnt/e/_/Orca/Projects/ctf/tools/vendor-ctf-skills/scripts/install_ctf_tools.sh' bash /root/provision.sh"

# 4) Apply wsl.conf (default user) by terminating the distro.
wsl --terminate $Distro
Write-Host "Done. Enter with:  wsl -d $Distro"
