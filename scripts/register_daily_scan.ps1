$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = (Get-Command python).Source
$TaskName = "Rahul Local Job Finder Daily Scan"
$Action = New-ScheduledTaskAction -Execute $Python -Argument "-m app.tasks scan" -WorkingDirectory $ProjectRoot
$Trigger = New-ScheduledTaskTrigger -Daily -At 9:00AM
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Daily local job scan for Rahul Job Finder." -Force
Write-Host "Registered task: $TaskName"
