# Mock every WSL call: this suite never imports, terminates, or changes a distro.
$ErrorActionPreference = 'Stop'
$SourceDir = Join-Path $PSScriptRoot '..\tools\wsl'
$TempRoot = Join-Path ([IO.Path]::GetTempPath()) ('ctf-wsl-tests-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $TempRoot | Out-Null
$FixtureDir = Join-Path $TempRoot "student's repo\tools\wsl"
New-Item -ItemType Directory -Path $FixtureDir -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $SourceDir 'setup-ubuntu-ctf.ps1') -Destination $FixtureDir
Copy-Item -LiteralPath (Join-Path $SourceDir 'provision-ubuntu-ctf.sh') -Destination $FixtureDir
$SetupScript = Join-Path $FixtureDir 'setup-ubuntu-ctf.ps1'
$Tarball = Join-Path $TempRoot 'test rootfs.tar'
Set-Content -LiteralPath $Tarball -Value 'not a real archive; WSL is mocked'
$global:CtfWslMock = @{
    Calls = New-Object 'System.Collections.Generic.List[object]'
    Mode = ''
}

function global:wsl.exe {
    $global:CtfWslMock.Calls.Add([object]@($args))
    $global:LASTEXITCODE = 0
    if ($args[0] -eq '--list') {
        if ($global:CtfWslMock.Mode -eq 'list-failure') { $global:LASTEXITCODE = 31 }
        elseif ($global:CtfWslMock.Mode -eq 'existing') { "u`0b`0u`0n`0t`0u`0-`0c`0t`0f`0" }
        return
    }
    if ($args[0] -eq '--import' -and $global:CtfWslMock.Mode -eq 'import-failure') { $global:LASTEXITCODE = 32 }
    if ($args -contains 'env' -and $global:CtfWslMock.Mode -eq 'provision-failure') { $global:LASTEXITCODE = 33 }
    if ($args[0] -eq '--terminate' -and $global:CtfWslMock.Mode -eq 'terminate-failure') { $global:LASTEXITCODE = 34 }
    if ($args -contains 'docker' -and $global:CtfWslMock.Mode -eq 'docker-failure') { $global:LASTEXITCODE = 35 }
}

function Assert-True($Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

try {
    foreach ($mode in @('existing', 'list-failure', 'import-failure', 'provision-failure', 'terminate-failure', 'docker-failure', 'success', 'docker-success')) {
        $global:CtfWslMock.Mode = $mode
        $global:CtfWslMock.Calls.Clear()
        $install = Join-Path $TempRoot $mode
        $failure = $null
        $noDocker = $mode -notlike 'docker-*'
        try { & $SetupScript -Distro ubuntu-ctf -Tarball $Tarball -InstallDir $install -NoDocker:$noDocker }
        catch { $failure = $_.Exception.Message }
        if ($mode -in @('success', 'docker-success')) {
            Assert-True ($null -eq $failure) "Success path failed: $failure"
            $expectedCount = if ($noDocker) { 4 } else { 5 }
            Assert-True ($global:CtfWslMock.Calls.Count -eq $expectedCount) 'Unexpected WSL command count.'
            Assert-True ($global:CtfWslMock.Calls[1][-2] -eq '--version' -and $global:CtfWslMock.Calls[1][-1] -eq '2') 'WSL2 flag missing.'
            $dockerArg = if ($noDocker) { 'INSTALL_DOCKER=0' } else { 'INSTALL_DOCKER=1' }
            Assert-True ($global:CtfWslMock.Calls[2] -contains $dockerArg) 'Docker option missing.'
            Assert-True ($global:CtfWslMock.Calls[2] -contains '-s') 'Provisioning must stream source to bash -s.'
            $repoArg = @($global:CtfWslMock.Calls[2] | Where-Object { $_ -like 'REPO=*' })[0]
            Assert-True ($repoArg.EndsWith("/student's repo")) 'Repo path lost apostrophe/space in argv.'
        } else {
            Assert-True ($null -ne $failure) "Failure was ignored: $mode"
            $expectedCount = @{ existing = 1; 'list-failure' = 1; 'import-failure' = 2; 'provision-failure' = 3; 'terminate-failure' = 4; 'docker-failure' = 5 }[$mode]
            Assert-True ($global:CtfWslMock.Calls.Count -eq $expectedCount) "Ran commands after failure: $mode ($failure)"
        }
        Write-Output "PASS $mode"
    }
} finally {
    Remove-Item Function:\wsl.exe
    Remove-Variable -Name CtfWslMock -Scope Global
    # Verify cleanup stays in this suite's specifically-created temp directory.
    $resolvedTemp = (Resolve-Path -LiteralPath $TempRoot).ProviderPath
    $systemTemp = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
    if ($resolvedTemp.StartsWith($systemTemp, [StringComparison]::OrdinalIgnoreCase) -and
        [IO.Path]::GetFileName($resolvedTemp).StartsWith('ctf-wsl-tests-')) {
        Remove-Item -LiteralPath $resolvedTemp -Recurse -Force
    }
}
