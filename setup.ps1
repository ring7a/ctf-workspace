# Offline agent-asset setup. This does not install WSL or either model CLI.
# Upstream downloads are review-only and never overwrite the vendored assets.
[CmdletBinding()]
param([switch]$FetchUpstream)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$Root = [System.IO.Path]::GetFullPath($PSScriptRoot)

function Invoke-CheckedNative {
    param([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Executable failed with exit code $LASTEXITCODE" }
}

$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) { throw "Python 3.11+ is required. Or run python -I tools/check-workspace.py --sync inside ubuntu-ctf." }
Invoke-CheckedNative $Python.Source @("-I", "-c", "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)")
Invoke-CheckedNative $Python.Source @("-I", (Join-Path $Root "tools/check-workspace.py"), "--sync")

if ($FetchUpstream) {
    $Git = Get-Command git -ErrorAction Stop
    $Pin = (Get-Content -LiteralPath (Join-Path $Root "tools/vendor-ctf-skills/PINNED_COMMIT.txt") -Raw).Trim()
    if ($Pin -notmatch '^[0-9a-f]{40}$') { throw "Invalid upstream commit pin" }
    $TempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    $Review = [System.IO.Path]::GetFullPath((Join-Path $TempRoot ("ctf-upstream-review-" + [guid]::NewGuid().ToString("N"))))
    if (-not $Review.StartsWith($TempRoot, [System.StringComparison]::OrdinalIgnoreCase) -or (Test-Path -LiteralPath $Review)) {
        throw "Invalid or existing review directory: $Review"
    }
    Write-Host "Fetching pinned upstream into review-only directory: $Review"
    Invoke-CheckedNative $Git.Source @("clone", "--no-checkout", "https://github.com/ljagiello/ctf-skills", $Review)
    Invoke-CheckedNative $Git.Source @("-C", $Review, "checkout", "--detach", $Pin)
    $Actual = & $Git.Source -C $Review rev-parse HEAD
    if ($LASTEXITCODE -ne 0 -or $Actual.Trim() -ne $Pin) { throw "Upstream pin verification failed; retained $Review for inspection" }
    foreach ($Asset in @("LICENSE", "scripts/install_ctf_tools.sh", "solve-challenge/SKILL.md", "ctf-writeup/SKILL.md")) {
        if (-not (Test-Path -LiteralPath (Join-Path $Review $Asset) -PathType Leaf)) { throw "Pinned source missing $Asset" }
    }
    Write-Host "Verified $Pin. Review changes against .claude/skills; preserve docs/SKILL-INTEGRATION.md adjustments."
    Write-Host "No workspace files were replaced by upstream. Review directory retained: $Review"
}
Write-Host "Agent assets ready. See docs/BOOTSTRAP.md for runtime setup and verification."
