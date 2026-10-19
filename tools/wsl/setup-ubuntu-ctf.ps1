# Import a NEW WSL2 distro; never reprovision an existing registration.
# Usage (Windows PowerShell 5.1 or PowerShell 7):
#   powershell -File tools\wsl\setup-ubuntu-ctf.ps1 [-Tarball rootfs.tar.gz] [-NoDocker]
param(
  [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]*$')]
  [string]$Distro = "ubuntu-ctf",
  [string]$InstallDir = "",
  [string]$Tarball = "",
  [switch]$NoDocker
)
$ErrorActionPreference = "Stop"

function Invoke-WslChecked {
  param([string[]]$ArgumentList)
  & wsl.exe @ArgumentList
  if ($LASTEXITCODE -ne 0) { throw "wsl.exe failed (exit $LASTEXITCODE): $($ArgumentList -join ' ')" }
}

function ConvertTo-WslPath([string]$Path) {
  $full = (Resolve-Path -LiteralPath $Path).ProviderPath
  if ($full -notmatch '^[A-Za-z]:\\') { throw "Use a local Windows drive path: $full" }
  return "/mnt/$($full.Substring(0,1).ToLower())$($full.Substring(2) -replace '\\','/')"
}

Get-Command wsl.exe -ErrorAction Stop | Out-Null
$registered = @(Invoke-WslChecked -ArgumentList @('--list', '--quiet'))
$registered = @($registered | ForEach-Object { ($_ -replace "`0", '').Trim() })
if ($registered -contains $Distro) {
  throw "Distro '$Distro' already exists; no changes made. Choose a new -Distro and -InstallDir."
}

$RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).ProviderPath
$RepoWsl = ConvertTo-WslPath $RepoRoot
$prov = Join-Path $PSScriptRoot 'provision-ubuntu-ctf.sh'
if (-not (Test-Path -LiteralPath $prov -PathType Leaf)) { throw "Missing $prov" }
if (-not $InstallDir) { $InstallDir = Join-Path $env:USERPROFILE "WSL\$Distro" }
$InstallDir = [IO.Path]::GetFullPath($InstallDir)
if (Test-Path -LiteralPath $InstallDir) {
  if (-not (Test-Path -LiteralPath $InstallDir -PathType Container)) { throw "Not a directory: $InstallDir" }
  if (@(Get-ChildItem -LiteralPath $InstallDir -Force).Count) { throw "Install directory is not empty: $InstallDir" }
}

if (-not $Tarball) {
  $Tarball = Get-AppxPackage *Ubuntu* | ForEach-Object {
    Join-Path $_.InstallLocation 'install.tar.gz'
  } | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
  if (-not $Tarball) { throw 'No Ubuntu rootfs tarball found. Pass -Tarball with an Ubuntu rootfs archive.' }
}
if (-not (Test-Path -LiteralPath $Tarball -PathType Leaf)) { throw "Rootfs tarball not found: $Tarball" }
$Tarball = (Resolve-Path -LiteralPath $Tarball).ProviderPath
Write-Host "Importing NEW distro $Distro -> $InstallDir (WSL2)"
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Invoke-WslChecked -ArgumentList @('--import', $Distro, $InstallDir, $Tarball, '--version', '2')

# Pass paths as argv, never interpolate them into shell source. Strip CRLF on stdin.
$docker = if ($NoDocker) { '0' } else { '1' }
$provisionText = (Get-Content -LiteralPath $prov -Encoding UTF8 -Raw).Replace("`r", '')
$provisionText | & wsl.exe -d $Distro -u root -- env "REPO=$RepoWsl" "INSTALL_DOCKER=$docker" bash -s
if ($LASTEXITCODE -ne 0) {
  throw "Provisioning failed (exit $LASTEXITCODE). Distro '$Distro' is retained for diagnosis; it was not deleted."
}
Invoke-WslChecked -ArgumentList @('--terminate', $Distro)
if (-not $NoDocker) {
  Invoke-WslChecked -ArgumentList @('-d', $Distro, '-u', 'root', '--', 'docker', 'info', '--format', '{{.ServerVersion}}')
}
Write-Host "Done. Enter with: wsl -d $Distro"
