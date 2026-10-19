# Host wrapper for the portable Volatility 3 Windows build. Adds this folder's symbols/ and plugins/.
# usage: powershell -NoProfile -File tools/volatility/vol.ps1 -f <image> <plugin> [args]
#        $env:CTF_VOL_EXE = 'D:\tools\volatility3-win-exes-2.28.2\vol.exe'   # or drop vol.exe into tools/volatility/bin/
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$VolArgs)
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$exe = $env:CTF_VOL_EXE
if (-not $exe) { $exe = Join-Path $here 'bin\vol.exe' }
if (-not (Test-Path -LiteralPath $exe)) {
    throw "vol.exe not found. Set CTF_VOL_EXE or place the portable build at tools\volatility\bin\vol.exe (https://github.com/volatilityfoundation/volatility3/releases, volatility3-win-exes-*.zip). Inside ubuntu-ctf use tools/volatility/vol.sh instead."
}
& $exe -s (Join-Path $here 'symbols') -p (Join-Path $here 'plugins') @VolArgs
exit $LASTEXITCODE
