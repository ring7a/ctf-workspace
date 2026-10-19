param(
    [ValidateSet('all', 'rea')][string]$Component = 'rea',
    [switch]$Check,
    [switch]$RegisterOnly
)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskArgs = @('-I', (Join-Path $PSScriptRoot 'integrations\setup.py'), '--component', $Component)
if ($Check) { $taskArgs += '--check' }
if ($RegisterOnly) { $taskArgs += '--register-only' }
& python @taskArgs
if ($LASTEXITCODE -ne 0) { throw "Integration setup failed with exit code $LASTEXITCODE. See the diagnostic above." }
