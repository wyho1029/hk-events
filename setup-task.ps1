# 注冊每日 Windows 排程，喺住宅 IP 刷新 hk-events 資料（避開雲端 403）
# 用法：右 click → Run with PowerShell（唔使 admin，注冊到 user scope）
# 移除：Unregister-ScheduledTask -TaskName HKEventsRefresh -Confirm:$false

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$taskName  = "HKEventsRefresh"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$runScript = Join-Path $scriptDir "refresh.ps1"
if (-not (Test-Path $runScript)) { Write-Host "[!] 搵唔到 $runScript" -ForegroundColor Red; exit 1 }

$service = New-Object -ComObject Schedule.Service
$service.Connect()
$folder = $service.GetFolder("\")
$task = $service.NewTask(0)

$task.RegistrationInfo.Description = "每日 13:00 喺住宅 IP 刷新 wmoov 電影 + 博客來書榜（GitHub Actions 雲端 IP 被 403 擋）"
$task.RegistrationInfo.Author = $env:USERNAME

$task.Settings.Enabled = $true
$task.Settings.StartWhenAvailable = $true                 # 部機當時未開就開機後補跑
$task.Settings.AllowDemandStart = $true
$task.Settings.DisallowStartIfOnBatteries = $false
$task.Settings.StopIfGoingOnBatteries = $false
$task.Settings.RunOnlyIfNetworkAvailable = $true
$task.Settings.ExecutionTimeLimit = "PT30M"
$task.Settings.MultipleInstances = 2                      # 撞咗就唔再開

# Daily trigger (type 2 = TASK_TRIGGER_DAILY)，13:00 本地時間
$trigger = $task.Triggers.Create(2)
$trigger.StartBoundary = (Get-Date -Hour 13 -Minute 0 -Second 0).ToString("yyyy-MM-ddTHH:mm:ss")
$trigger.DaysInterval = 1
$trigger.Enabled = $true

# Action：powershell 行 refresh.ps1
$action = $task.Actions.Create(0)
$action.Path = "powershell.exe"
$action.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$runScript`""
$action.WorkingDirectory = $scriptDir

try {
    $folder.RegisterTaskDefinition($taskName, $task, 6, $null, $null, 3, $null) | Out-Null
} catch {
    Write-Host "[!] 注冊失敗：$($_.Exception.Message)" -ForegroundColor Red; exit 1
}

$info = Get-ScheduledTaskInfo -TaskName $taskName
Write-Host ""
Write-Host "[OK] 注冊成功！" -ForegroundColor Green
Write-Host "  Task     : $taskName（每日 13:00）"
Write-Host "  Next run : $($info.NextRunTime)"
Write-Host "  即時測試 : Start-ScheduledTask -TaskName $taskName"
Write-Host "  移除     : Unregister-ScheduledTask -TaskName $taskName -Confirm:`$false"
