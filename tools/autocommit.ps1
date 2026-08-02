<#
.SYNOPSIS
    Следит за файлами проекта и коммитит изменения с пушем.

.DESCRIPTION
    Скрипт опрашивает `git status` раз в несколько секунд. Так проще и надёжнее
    FileSystemWatcher: обработчики событий выполняются в отдельном runspace, где
    переменные скрипта недоступны, и отслеживание молча ничего не делает. К тому
    же git сам применяет .gitignore, так что тяжёлые каталоги (база, кэш матчей,
    node_modules, .venv) в опрос не попадают.

    Изменения копятся и уходят одним коммитом после паузы в правках (по
    умолчанию 45 секунд) — иначе каждое сохранение файла в редакторе давало бы
    отдельный коммит.

.PARAMETER DebounceSeconds
    Сколько секунд тишины ждать перед коммитом.

.PARAMETER PollSeconds
    Как часто опрашивать состояние репозитория.

.PARAMETER NoPush
    Только коммитить, не пушить.

.EXAMPLE
    pwsh -File tools/autocommit.ps1
    pwsh -File tools/autocommit.ps1 -DebounceSeconds 120 -NoPush
#>
[CmdletBinding()]
param(
    [int]$DebounceSeconds = 45,
    [int]$PollSeconds = 5,
    [switch]$NoPush
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

if (-not (Test-Path (Join-Path $repo '.git'))) {
    throw "не репозиторий git: $repo"
}

Write-Host "Слежу за $repo" -ForegroundColor Cyan
Write-Host "пауза перед коммитом: $DebounceSeconds с, пуш: $(-not $NoPush)" -ForegroundColor DarkGray
Write-Host "Ctrl+C — остановить`n" -ForegroundColor DarkGray

$lastStatus = $null
$quietSince = $null

while ($true) {
    $status = (git status --porcelain | Out-String).Trim()

    if ($status -ne $lastStatus) {
        # Состояние изменилось — отсчёт тишины начинается заново.
        $lastStatus = $status
        $quietSince = Get-Date
        Start-Sleep -Seconds $PollSeconds
        continue
    }

    $readyToCommit = $status -and $quietSince -and
                     ((Get-Date) - $quietSince).TotalSeconds -ge $DebounceSeconds

    if ($readyToCommit) {
        $files = ($status -split "`n" | Where-Object { $_ }).Count
        git add -A | Out-Null

        # Проверяем именно индекс: неотслеживаемый файл, целиком попавший под
        # .gitignore, состояние меняет, а коммитить в нём нечего.
        if (git diff --staged --quiet) {
            $lastStatus = (git status --porcelain | Out-String).Trim()
            $quietSince = $null
            Start-Sleep -Seconds $PollSeconds
            continue
        }

        $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm'
        git commit -q -m "auto: правки от $stamp ($files файлов)"
        Write-Host "[$stamp] коммит: $files файлов" -ForegroundColor Green

        if (-not $NoPush) {
            git push -q 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) {
                Write-Host "                  запушено" -ForegroundColor DarkGreen
            } else {
                # Нет сети или пуш отклонён — коммит уже сохранён локально,
                # следующая попытка отправит и его.
                Write-Host "                  пуш не удался, коммит остался локально" -ForegroundColor Yellow
            }
        }

        $lastStatus = (git status --porcelain | Out-String).Trim()
        $quietSince = $null
    }

    Start-Sleep -Seconds $PollSeconds
}
