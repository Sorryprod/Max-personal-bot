# Интерактивная настройка .env и запуск решения в Docker (Windows PowerShell 5.1+ / PowerShell 7).
# Запуск: powershell -ExecutionPolicy Bypass -File .\install.ps1
# Повторный запуск безопасен: уже заданные значения предлагаются по умолчанию.
# Ошибки нативных команд проверяются по $LASTEXITCODE: в PowerShell 5.1 режим Stop
# превращает любой вывод docker в stderr в исключение.
$ErrorActionPreference = 'Continue'
Set-Location $PSScriptRoot
[Console]::OutputEncoding = [Text.Encoding]::UTF8

$EnvFile = Join-Path $PSScriptRoot '.env'
$Utf8 = New-Object Text.UTF8Encoding($false)

function Die($msg) { Write-Host "`nОшибка: $msg" -ForegroundColor Red; exit 1 }

function Get-EnvValue($key) {
    if (-not (Test-Path $EnvFile)) { return '' }
    $line = [IO.File]::ReadAllLines($EnvFile, $Utf8) | Where-Object { $_ -like "$key=*" } | Select-Object -Last 1
    if ($line) { return $line.Substring($key.Length + 1) } else { return '' }
}

function Set-EnvValue($key, $value) {
    $lines = [Collections.Generic.List[string]]([IO.File]::ReadAllLines($EnvFile, $Utf8))
    $idx = $lines.FindIndex({ param($l) $l -like "$key=*" })
    if ($idx -ge 0) { $lines[$idx] = "$key=$value" } else { $lines.Add("$key=$value") }
    [IO.File]::WriteAllText($EnvFile, ($lines -join "`n") + "`n", $Utf8)
}

function New-RandomHex { -join ((1..16) | ForEach-Object { '{0:x2}' -f (Get-Random -Maximum 256) }) }

# Спрашивает значение переменной; Enter оставляет текущее.
function Ask($key, $prompt, [switch]$Secret) {
    $current = Get-EnvValue $key
    $shown = $current
    if ($Secret -and $current) { $shown = 'задан, Enter — оставить' }
    $question = if ($shown) { "$prompt [$shown]" } else { $prompt }
    $answer = Read-Host $question
    if ($answer) { Set-EnvValue $key $answer.Trim() }
}

function Compose { & docker compose @args; if ($LASTEXITCODE -ne 0) { Die "docker compose $args завершился с ошибкой" } }

function Wait-Healthy {
    Write-Host -NoNewline 'Ждём готовности api'
    for ($i = 0; $i -lt 60; $i++) {
        $id = (& docker compose ps -q api) | Select-Object -First 1
        if ($id) {
            $status = & docker inspect -f '{{.State.Health.Status}}' $id 2>$null
            if ($status -eq 'healthy') { Write-Host ' — готово'; return }
        }
        Write-Host -NoNewline '.'; Start-Sleep 2
    }
    Write-Host ''
    & docker compose logs --tail 30 api
    Die 'api не поднялся за 2 минуты — см. логи выше (docker compose logs api)'
}

function Get-TunnelUrl {
    $logs = (& docker compose --profile tunnel logs tunnel 2>$null) -join "`n"
    $found = [regex]::Matches($logs, 'https://[A-Za-z0-9.-]+\.cloudpub\.[a-z]+')
    if ($found.Count) { return $found[$found.Count - 1].Value } else { return '' }
}

# --- 1. Проверка окружения ---
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Die 'не найден docker — установите Docker Desktop' }
& docker compose version *> $null; if ($LASTEXITCODE -ne 0) { Die 'нужен Docker Compose v2 (команда «docker compose»)' }
& docker info *> $null; if ($LASTEXITCODE -ne 0) { Die 'Docker не запущен — запустите Docker Desktop' }

# --- 2. .env ---
if (-not (Test-Path $EnvFile)) {
    [IO.File]::WriteAllText($EnvFile, [IO.File]::ReadAllText((Join-Path $PSScriptRoot '.env.example'), $Utf8), $Utf8)
    Set-EnvValue 'POSTGRES_PASSWORD' (New-RandomHex)
    Write-Host 'Создан .env из .env.example (пароль БД сгенерирован).'
}

Write-Host "`nТокен бота MAX: кабинет MAX для бизнеса → чат-бот → Интеграция (на хакатоне — выдан организаторами)."
do {
    Ask 'BOT_TOKEN' 'BOT_TOKEN' -Secret
    if (-not (Get-EnvValue 'BOT_TOKEN')) { Write-Host 'Без токена бот не запустится.' }
} until (Get-EnvValue 'BOT_TOKEN')

Write-Host "`nКак MAX будет доставлять апдейты и открывать мини-приложение?"
Write-Host '  1) Туннель CloudPub — публичный HTTPS без своего сервера (рекомендуется, нужен бесплатный аккаунт cloudpub.ru)'
Write-Host '  2) Свой публичный HTTPS-адрес на порту 443 (reverse-proxy на localhost:8080, порт — API_PORT)'
Write-Host '  3) Только чат-бот, без публичного адреса (long polling; мини-приложение работодателя недоступно)'
$mode = Read-Host 'Выбор [1]'
if (-not $mode) { $mode = '1' }

$profileArgs = @()
switch ($mode) {
    '1' {
        Write-Host 'Токен агента CloudPub: cloudpub.ru → личный кабинет → «Токен» (или «Установка»).'
        do { Ask 'CLOUDPUB_TOKEN' 'CLOUDPUB_TOKEN' -Secret } until (Get-EnvValue 'CLOUDPUB_TOKEN')
        $profileArgs = @('--profile', 'tunnel')
    }
    '2' {
        do {
            Ask 'PUBLIC_URL' 'PUBLIC_URL (https://…, без слеша в конце)'
            $ok = (Get-EnvValue 'PUBLIC_URL') -like 'https://*'
            if (-not $ok) { Write-Host 'Нужен адрес вида https://…' }
        } until ($ok)
    }
    '3' {
        Set-EnvValue 'UPDATES_MODE' 'polling'
        Set-EnvValue 'WEBAPP_OPEN_MODE' 'native'
    }
    default { Die "неизвестный вариант: $mode" }
}

# --- 3. Запуск ---
if ($mode -eq '1') {
    # Адрес туннеля известен только после его старта: сначала поднимаем стек в режиме, которому адрес не нужен.
    if (-not (Get-EnvValue 'PUBLIC_URL')) {
        Set-EnvValue 'UPDATES_MODE' 'polling'
        Set-EnvValue 'WEBAPP_OPEN_MODE' 'native'
    }
    Write-Host "`nСборка и запуск (db, api, tunnel)…"
    Compose @profileArgs up -d --build
    Write-Host -NoNewline 'Ждём публичный адрес туннеля'
    $url = ''
    for ($i = 0; $i -lt 45 -and -not $url; $i++) {
        $url = Get-TunnelUrl
        if (-not $url) { Write-Host -NoNewline '.'; Start-Sleep 2 }
    }
    Write-Host ''
    if (-not $url) {
        & docker compose --profile tunnel logs --tail 20 tunnel
        Die 'туннель не выдал адрес — проверьте CLOUDPUB_TOKEN'
    }
    Write-Host "Адрес туннеля: $url"
    Set-EnvValue 'PUBLIC_URL' $url
}

if ($mode -ne '3') {
    $publicUrl = Get-EnvValue 'PUBLIC_URL'
    Set-EnvValue 'UPDATES_MODE' 'webhook'
    if (-not (Get-EnvValue 'WEBHOOK_SECRET')) { Set-EnvValue 'WEBHOOK_SECRET' (New-RandomHex) }
    Write-Host "`nМини-приложение открывается нативно, только если в кабинете MAX для бизнеса у бота прописан URL"
    Write-Host "  $publicUrl/app/"
    Write-Host 'Иначе кнопки бота откроют ту же страницу по подписанной ссылке (WEBAPP_OPEN_MODE=link).'
    $native = Read-Host 'URL мини-приложения прописан в настройках бота? [y/N]'
    if ($native -match '^[yYдД]') { Set-EnvValue 'WEBAPP_OPEN_MODE' 'native' } else { Set-EnvValue 'WEBAPP_OPEN_MODE' 'link' }
}

Write-Host "`nЗапуск…"
Compose @profileArgs up -d --build
Wait-Healthy

$logs = (& docker compose logs api 2>$null) -join "`n"
$bots = [regex]::Matches($logs, 'Бот @([A-Za-z0-9_]+)')
$bot = if ($bots.Count) { $bots[$bots.Count - 1].Groups[1].Value } else { '' }
$port = Get-EnvValue 'API_PORT'; if (-not $port) { $port = '8080' }

Write-Host "`nГотово. Решение запущено: апдейты — $(Get-EnvValue 'UPDATES_MODE'), мини-приложение — $(Get-EnvValue 'WEBAPP_OPEN_MODE')." -ForegroundColor Green
if ($bot) {
    Write-Host "  Бот:                   https://max.ru/$bot"
    Write-Host "  Демо-вакансия повара:  https://max.ru/$bot`?start=demo-povar"
}
if ($mode -ne '3') { Write-Host "  Мини-приложение:       $(Get-EnvValue 'PUBLIC_URL')/app/" }
Write-Host "  Проверка:              http://localhost:$port/health"
Write-Host "`nСценарий проверки — раздел «Пошаговый сценарий проверки» в README.md."
$stopCmd = (@('docker', 'compose') + $profileArgs + 'stop') -join ' '
Write-Host "Логи: docker compose logs -f api · остановка: $stopCmd"
