param([switch]$Apply, [switch]$InstallAfter)
$ErrorActionPreference = 'Stop'
$taskIdentity = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
$taskAdmin = $taskIdentity.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
$taskService = Get-CimInstance Win32_Service -Filter "Name='WslService'"
$taskVMs = @(Get-Process -ErrorAction SilentlyContinue | Where-Object {
    $_.ProcessName -match '^(vmmem|vmmemWSL|vmwp|wslhost)$'
})
[pscustomobject]@{ServiceState=$taskService.State; ServicePid=$taskService.ProcessId;
    Administrator=$taskAdmin; ObservedVMProcesses=$taskVMs.Count; ApplyRequested=$Apply.IsPresent} | ConvertTo-Json
if (-not $Apply) { return }
if (-not $taskAdmin) { throw 'Run this reviewed script in an Administrator PowerShell. No elevation popup is opened automatically.' }
if ($taskVMs.Count -ne 0) { throw 'A VM or WSL host process exists. Refusing to interrupt an existing workload.' }
if ($taskService.State -eq 'Stop Pending') {
    $taskProcess = Get-Process -Id $taskService.ProcessId -ErrorAction Stop
    if ($taskProcess.ProcessName -ne 'wslservice') { throw 'Service process identity changed; refusing to stop it.' }
    $taskFreshService = Get-CimInstance Win32_Service -Filter "Name='WslService'"
    $taskFreshVMs = @(Get-Process -ErrorAction SilentlyContinue | Where-Object {
        $_.ProcessName -match '^(vmmem|vmmemWSL|vmwp|wslhost)$'
    })
    if ($taskFreshService.State -ne 'Stop Pending' -or $taskFreshService.ProcessId -ne $taskProcess.Id -or $taskFreshVMs.Count -ne 0) {
        throw 'Service or workload state changed during diagnosis; refusing to stop.'
    }
    Stop-Process -InputObject $taskProcess -Force -ErrorAction Stop
    $taskController = Get-Service WslService
    $taskController.WaitForStatus([System.ServiceProcess.ServiceControllerStatus]::Stopped,
        [TimeSpan]::FromSeconds(20))
    Start-Service -Name WslService -ErrorAction Stop
} elseif ($taskService.State -eq 'Stopped') {
    Start-Service -Name WslService -ErrorAction Stop
} elseif ($taskService.State -ne 'Running') {
    throw 'Unexpected service transition; no other service or machine is restarted.'
}
Get-Service WslService | Select-Object Name,Status | ConvertTo-Json
if ($InstallAfter) { & (Join-Path $PSScriptRoot 'setup-integrations.ps1') }
