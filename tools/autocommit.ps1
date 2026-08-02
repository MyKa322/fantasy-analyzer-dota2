<#
.SYNOPSIS
    Следит за файлами проекта и коммитит изменения с пушем.

.DESCRIPTION
    Изменения копятся и уходят одним коммитом после паузы в правках (по
    умолчанию 45 секунд). Без такой паузы каждое сохранение файла редактором
    давало бы отдельный коммит, а история превращалась бы в мусор.

    Что не отслеживается — берётся из .gitignore: база, кэш матчей, node_modules,
    .venv. Так что тяжёлые каталоги watcher не трогает.

.PARAMETER DebounceSeconds
    Сколько секунд тишины ждать перед коммитом.

.PARAMETER NoPush
    Только коммитить, не пушить.

.EXAMPLE
    pwsh -File tools/autocommit.ps1
    pwsh -File tools/autocommit.ps1 -DebounceSeconds 120 -NoPush
#>
[CmdletBinding()]
param(
    [int]$DebounceSeconds = 45,
    [switch]$NoPush
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

if (-not (Test-Path (Join-Path $repo '.git'))) {
    Write-Error "не репозиторий git: $repo"
}

Write-Host "Слежу за $repo (пауза $DebounceSeconds с, пуш: $(-not $NoPush))" -ForegroundColor Cyan
Write-Host "Ctrl+C — остановить`n" -ForegroundColor DarkGray

function Invoke-AutoCommit {
    # Порядок важен: сначала узнаём, есть ли что коммитить, и только потом
    # трогаем индекс — иначе пустой коммит на каждое срабатывание таймера.
    $status = git status --porcelain
    if (-not $status) { return }

    $files = ($status | Measure-Object).Count
    git add -A | Out-Null

    $staged = git diff --staged --stat
    if (-not $staged) { return }

    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm'
    git commit -m "auto: правки от $stamp ($files файлов)" | Out-Null
    Write-Host "[$stamp] коммит: $files файлов" -ForegroundColor Green

    if (-not $NoPush) {
        try {
            git push 2>&1 | Out-Null
            Write-Host "           запушено" -ForegroundColor DarkGreen
        } catch {
            # Нет сети или отклонён пуш — коммит уже сохранён локально,
            # следующая попытка отправит и его.
            Write-Host "           пуш не удался: $_" -ForegroundColor Yellow
        }
    }
}

$watcher = [System.IO.FileSystemWatcher]::new($repo)
$watcher.IncludeSubdirectories = $true
$watcher.EnableRaisingEvents = $true
$watcher.NotifyFilter = [System.IO.NotifyFilters]::FileName -bor
                        [System.IO.NotifyFilters]::LastWrite -bor
                        [System.IO.NotifyFilters]::DirectoryName

# Каталоги, которые шумят постоянно и всё равно не попадают в git.
$ignored = '\\(\.git|\.venv|node_modules|__pycache__|\.pytest_cache|dist|data)\\'

$script:lastChange = $null
$handler = {
    if ($Event.SourceEventArgs.FullPath -notmatch $using:ignored) {
        $script:lastChange = Get-Date
    }
}

$subscriptions = @(
    Register-ObjectEvent $watcher Changed -Action $handler
    Register-ObjectEvent $watcher Created -Action $handler
    Register-ObjectEvent $watcher Deleted -Action $handler
    Register-ObjectEvent $watcher Renamed -Action $handler
)

try {
    while ($true) {
        Start-Sleep -Seconds 5
        if ($script:lastChange -and
            ((Get-Date) - $script:lastChange).TotalSeconds -ge $DebounceSeconds) {
            $script:lastChange = $null
            Invoke-AutoCommit
        }
    }
} finally {
    $subscriptions | Unregister-Event -Force
    $watcher.Dispose()
    Write-Host "`nостановлено" -ForegroundColor Cyan
}
