# 本地刷新 hk-events 資料（住宅 IP，wmoov 電影 + 博客來書榜唔會被 403 擋）
# 由 setup-task.ps1 注冊嘅 Windows 排程每日觸發，或者手動右 click Run。
# 只更新 docs/events.json + docs/books.json，唔掂 seen.json（Discord 狀態交俾 Actions）。

try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $env:PYTHONIOENCODING = "utf-8"
    Set-Location $PSScriptRoot

    $logDir = Join-Path $PSScriptRoot "logs"
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
    $log = Join-Path $logDir ("refresh_" + (Get-Date -Format "yyyy-MM-dd_HHmmss") + ".log")
    function Note($m) { "$(Get-Date -Format 'HH:mm:ss')  $m" | Tee-Object -FilePath $log -Append }

    Note "開始本地刷新"

    # 絕對路徑避開 Task Scheduler PATH 撞 Microsoft Store python stub
    $py = "C:\Users\WYHO\AppData\Local\Programs\Python\Python313\python.exe"
    if (-not (Test-Path $py)) {
        $py = (Get-Command python.exe -ErrorAction SilentlyContinue |
               Where-Object { $_.Source -notlike "*WindowsApps*" } |
               Select-Object -First 1).Source
    }
    Note "Python: $py"

    # 先攞 origin 最新（含 Actions 嘅資料 commit），保持乾淨基礎
    # ($LASTEXITCODE 喺 native | cmdlet pipeline 反映 native command 即 git 嘅 exit code)
    git pull --rebase --autostash origin master 2>&1 | Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 0) {
        Note "[X] git pull 失敗 exit=$LASTEXITCODE，中止（唔好喺壞基礎上 push）"
        git rebase --abort 2>$null
        exit 1
    }

    Note "跑 scrape.py + books.py"
    & cmd.exe /c "`"$py`" scrape.py >> `"$log`" 2>&1"
    if ($LASTEXITCODE -ne 0) { Note "[X] scrape.py 失敗 exit=$LASTEXITCODE"; exit 1 }
    & cmd.exe /c "`"$py`" books.py  >> `"$log`" 2>&1"
    if ($LASTEXITCODE -ne 0) { Note "[X] books.py 失敗 exit=$LASTEXITCODE"; exit 1 }

    # Discord 推送狀態交俾 GitHub Actions，本地唔改
    git checkout -- state/seen.json 2>$null

    git add docs/events.json docs/books.json
    git diff --cached --quiet
    if ($LASTEXITCODE -eq 0) { Note "資料冇變，唔使 commit"; exit 0 }

    git commit -m ("chore: 本地刷新 wmoov/博客來 " + (Get-Date -Format "yyyy-MM-dd")) 2>&1 |
        Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 0) { Note "[X] git commit 失敗 exit=$LASTEXITCODE"; exit 1 }

    # push；Actions 可能喺我 pull 之後又 push，撞就 rebase（資料檔保留我份新嘅）再試
    $pushed = $false
    for ($i = 0; $i -lt 3; $i++) {
        git push origin master 2>&1 | Tee-Object -FilePath $log -Append
        if ($LASTEXITCODE -eq 0) { $pushed = $true; Note "push 成功"; break }
        Note "push 被拒，rebase 後重試 ($($i + 1))"
        git fetch origin 2>&1 | Tee-Object -FilePath $log -Append
        git rebase -X theirs origin/master 2>&1 | Tee-Object -FilePath $log -Append
    }
    if (-not $pushed) { Note "[X] push 重試 3 次都失敗，資料未上 GitHub"; exit 1 }
    Note "完成"
} catch {
    "[X] $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') Exception: $($_.Exception.Message)" |
        Tee-Object -FilePath $log -Append
    exit 1
}
