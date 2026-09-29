#!/usr/bin/env bash
# Интерактивная настройка .env и запуск решения в Docker (Linux, macOS, Git Bash на Windows).
# Повторный запуск безопасен: уже заданные значения предлагаются по умолчанию.
set -euo pipefail
cd "$(dirname "$0")"

ENV_FILE=.env

die() { printf '\nОшибка: %s\n' "$1" >&2; exit 1; }

get_env() {
  grep -E "^$1=" "$ENV_FILE" 2>/dev/null | tail -n 1 | cut -d= -f2- || true
}

set_env() {
  awk -v k="$1" -v v="$2" '
    $0 ~ "^" k "=" { if (!done) print k "=" v; done = 1; next }
    { print }
    END { if (!done) print k "=" v }
  ' "$ENV_FILE" > "$ENV_FILE.tmp" && mv "$ENV_FILE.tmp" "$ENV_FILE"
}

random_hex() { od -An -N16 -tx1 /dev/urandom | tr -d ' \n'; }

# ask ПЕРЕМЕННАЯ "Вопрос" [скрыть_значение] — спрашивает значение, Enter оставляет текущее.
ask() {
  local key=$1 prompt=$2 secret=${3:-} current answer shown
  current=$(get_env "$key")
  shown=$current
  if [ -n "$secret" ] && [ -n "$current" ]; then shown="задан, Enter — оставить"; fi
  if [ -n "$shown" ]; then read -r -p "$prompt [$shown]: " answer; else read -r -p "$prompt: " answer; fi
  if [ -n "$answer" ]; then set_env "$key" "$answer"; fi
}

compose() { docker compose "$@"; }

wait_healthy() {
  local id status i
  printf 'Ждём готовности api'
  for i in $(seq 1 60); do
    id=$(compose ps -q api)
    status=$(docker inspect -f '{{.State.Health.Status}}' "$id" 2>/dev/null || true)
    if [ "$status" = "healthy" ]; then printf ' — готово\n'; return 0; fi
    printf '.'; sleep 2
  done
  printf '\n'
  compose logs --tail 30 api
  die "api не поднялся за 2 минуты — см. логи выше (docker compose logs api)"
}

tunnel_url() {
  compose --profile tunnel logs tunnel 2>/dev/null \
    | grep -oE 'https://[A-Za-z0-9.-]+\.cloudpub\.[a-z]+' | tail -n 1 || true
}

# --- 1. Проверка окружения ---
command -v docker >/dev/null || die "не найден docker — установите Docker Engine 24+ или Docker Desktop"
docker compose version >/dev/null 2>&1 || die "нужен Docker Compose v2 (команда «docker compose»)"
docker info >/dev/null 2>&1 || die "Docker не запущен — запустите Docker Desktop / службу docker"

# --- 2. .env ---
if [ ! -f "$ENV_FILE" ]; then
  cp .env.example "$ENV_FILE"
  set_env POSTGRES_PASSWORD "$(random_hex)"
  echo "Создан .env из .env.example (пароль БД сгенерирован)."
fi

echo
echo "Токен бота MAX: кабинет MAX для бизнеса → чат-бот → Интеграция (на хакатоне — выдан организаторами)."
while :; do
  ask BOT_TOKEN "BOT_TOKEN" secret
  [ -n "$(get_env BOT_TOKEN)" ] && break
  echo "Без токена бот не запустится."
done

echo
echo "Как MAX будет доставлять апдейты и открывать мини-приложение?"
echo "  1) Туннель CloudPub — публичный HTTPS без своего сервера (рекомендуется, нужен бесплатный аккаунт cloudpub.ru)"
echo "  2) Свой публичный HTTPS-адрес на порту 443 (reverse-proxy на localhost:8080, порт — API_PORT)"
echo "  3) Только чат-бот, без публичного адреса (long polling; мини-приложение работодателя недоступно)"
read -r -p "Выбор [1]: " mode
mode=${mode:-1}

profile=
case $mode in
  1)
    echo "Токен агента CloudPub: cloudpub.ru → личный кабинет → «Токен» (или «Установка»)."
    while :; do
      ask CLOUDPUB_TOKEN "CLOUDPUB_TOKEN" secret
      [ -n "$(get_env CLOUDPUB_TOKEN)" ] && break
    done
    profile="--profile tunnel"
    ;;
  2)
    while :; do
      ask PUBLIC_URL "PUBLIC_URL (https://…, без слеша в конце)"
      case $(get_env PUBLIC_URL) in https://*) break ;; esac
      echo "Нужен адрес вида https://…"
    done
    ;;
  3)
    set_env UPDATES_MODE polling
    set_env WEBAPP_OPEN_MODE native
    ;;
  *) die "неизвестный вариант: $mode" ;;
esac

# --- 3. Запуск ---
if [ "$mode" = 1 ]; then
  # Адрес туннеля известен только после его старта: сначала поднимаем стек в режиме, которому адрес не нужен.
  if [ -z "$(get_env PUBLIC_URL)" ]; then
    set_env UPDATES_MODE polling
    set_env WEBAPP_OPEN_MODE native
  fi
  echo; echo "Сборка и запуск (db, api, tunnel)…"
  compose $profile up -d --build
  printf 'Ждём публичный адрес туннеля'
  url=
  for _ in $(seq 1 45); do
    url=$(tunnel_url)
    [ -n "$url" ] && break
    printf '.'; sleep 2
  done
  printf '\n'
  [ -n "$url" ] || { compose --profile tunnel logs --tail 20 tunnel; die "туннель не выдал адрес — проверьте CLOUDPUB_TOKEN"; }
  echo "Адрес туннеля: $url"
  set_env PUBLIC_URL "$url"
fi

if [ "$mode" != 3 ]; then
  public_url=$(get_env PUBLIC_URL)
  set_env UPDATES_MODE webhook
  [ -n "$(get_env WEBHOOK_SECRET)" ] || set_env WEBHOOK_SECRET "$(random_hex)"
  echo
  echo "Мини-приложение открывается нативно, только если в кабинете MAX для бизнеса у бота прописан URL"
  echo "  $public_url/app/"
  echo "Иначе кнопки бота откроют ту же страницу по подписанной ссылке (WEBAPP_OPEN_MODE=link)."
  read -r -p "URL мини-приложения прописан в настройках бота? [y/N]: " native
  case $native in y*|Y*|д*|Д*) set_env WEBAPP_OPEN_MODE native ;; *) set_env WEBAPP_OPEN_MODE link ;; esac
fi

echo; echo "Запуск…"
compose $profile up -d --build
wait_healthy

bot=$(compose logs api 2>/dev/null | sed -n 's/.*Бот @\([A-Za-z0-9_]*\).*/\1/p' | tail -n 1 || true)
port=$(get_env API_PORT); port=${port:-8080}

echo
echo "Готово. Решение запущено: апдейты — $(get_env UPDATES_MODE), мини-приложение — $(get_env WEBAPP_OPEN_MODE)."
[ -n "$bot" ] && echo "  Бот:                   https://max.ru/$bot"
[ -n "$bot" ] && echo "  Демо-вакансия повара:  https://max.ru/$bot?start=demo-povar"
[ "$mode" != 3 ] && echo "  Мини-приложение:       $(get_env PUBLIC_URL)/app/"
echo "  Проверка:              http://localhost:$port/health"
echo
echo "Сценарий проверки — раздел «Пошаговый сценарий проверки» в README.md."
echo "Логи: docker compose logs -f api · остановка: docker compose ${profile:+$profile }stop"
