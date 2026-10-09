# Create and provision a dedicated "ubuntu-ctf" WSL2 distro for CTF work.
# Portable: derives the repo root from its own location (no hardcoded paths).
# Does NOT touch any existing distro or change the default distro.
#
# Prereq: WSL2 engine present (`wsl --version` works) and an Ubuntu rootfs
# tarball available (an installed Ubuntu appx, or pass -Tarball).
#
# Usage:  pwsh -File tools\wsl\setup-ubuntu-ctf.ps1
param(
  [string]$Distro     = "ubuntu-ctf",
  [string]$InstallDir = "$env:USERPROFILE\WSL\ubuntu-ctf",
  [string]$Tarball    = ""
)
$ErrorActionPreference = "Stop"

# Convert a Windows path to its /mnt/<drive>/... WSL form in pure PowerShell.
# (Do NOT shell out to `wsl wslpath` — WSL interop eats the backslashes.)
function ConvertTo-WslPath([string]$p) {
  $full  = (Resolve-Path $p).Path
  $drive = $full.Substring(0,1).ToLower()
  $rest  = $full.Substring(2) -replace '\\','/'
  return "/mnt/$drive$rest"
}

# Repo root = two levels up from this script (tools/wsl -> repo).
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
# Same path as seen from inside WSL (e.g. E:\_\Orca\Projects\ctf-workspace -> /mnt/e/_/Orca/Projects/ctf-workspace).
$RepoWsl  = ConvertTo-WslPath $RepoRoot
Write-Host "Repo (Windows): $RepoRoot"
Write-Host "Repo (WSL):     $RepoWsl"

# 1) Locate an Ubuntu rootfs tarball (reuse installed appx by default; no download).
if (-not $Tarball) {
  $appx = (Get-AppxPackage *Ubuntu*).InstallLocation | Select-Object -First 1
  if (-not $appx) { throw "No Ubuntu appx found. Run `wsl --install -d Ubuntu --no-launch`, or pass -Tarball." }
  $Tarball = Join-Path $appx "install.tar.gz"
}
if (-not (Test-Path $Tarball)) { throw "Rootfs tarball not found: $Tarball" }
Write-Host "Using rootfs: $Tarball"

# 2) Import as a new distro (registers as root; no interactive user prompt).
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Write-Host "Importing $Distro -> $InstallDir ..."
wsl --import $Distro $InstallDir $Tarball

# 3) Run the provisioning script inside the distro as root, passing REPO.
$prov = Join-Path $PSScriptRoot "provision-ubuntu-ctf.sh"
if (-not (Test-Path $prov)) { throw "Missing $prov" }
$provWsl = ConvertTo-WslPath $prov
Write-Host "Provisioning (installs CTF tools; takes a while)..."
wsl -d $Distro -u root bash -c "sed 's/\r`$//' '$provWsl' > /root/provision.sh; REPO='$RepoWsl' bash /root/provision.sh"

# 4) Apply wsl.conf (default user) by terminating the distro.
wsl --terminate $Distro
Write-Host "Done. Enter with:  wsl -d $Distro"
