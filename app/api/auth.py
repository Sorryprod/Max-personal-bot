"""Авторизация мини-приложения: проверка подписи initData из MAX Bridge.

Алгоритм (https://dev.max.ru/docs/webapps/validation):
  secret_key = HMAC_SHA256(key="WebAppData", msg=BOT_TOKEN)
  data_check_string = отсортированные по ключу пары key=value (без hash), через "\\n"
  hash == hex(HMAC_SHA256(key=secret_key, msg=data_check_string))
user_id берётся только из проверенной подписи, а не из тела запроса.

Запасной вход (WEBAPP_OPEN_MODE=link, пока URL мини-приложения не прописан в настройках бота):
бот присылает в личный чат ссылку с токеном, подписанным сервером (HMAC от токена бота,
отдельный ключ), с ограниченным сроком жизни. Страница передаёт его в заголовке X-Login-Token.
"""

import base64
import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl, unquote

from fastapi import Header, HTTPException, Request

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class WebAppUser:
    id: int
    first_name: str = ""
    last_name: str = ""
    username: str = ""

    @property
    def full_name(self) -> str:
        return " ".join(p for p in (self.first_name, self.last_name) if p)


class InitDataError(Exception):
    pass


def _normalize(init_data: str) -> str:
    init_data = init_data.strip().lstrip("#?")
    # В URL запуска параметры могут прийти обёрнутыми: WebAppData=<urlencoded initData>
    if init_data.startswith("WebAppData="):
        init_data = unquote(init_data[len("WebAppData=") :])
    return init_data


def sign_init_data(fields: dict[str, str], bot_token: str) -> str:
    """Подписывает initData так же, как MAX. Используется в тестах."""
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    return hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()


def validate_init_data(init_data: str, bot_token: str, ttl_seconds: int, now: float | None = None) -> WebAppUser:
    if not init_data:
        raise InitDataError("initData отсутствует")
    data = dict(parse_qsl(_normalize(init_data), keep_blank_values=True))
    received = data.pop("hash", "")
    if not received:
        raise InitDataError("нет поля hash")
    if not hmac.compare_digest(sign_init_data(data, bot_token), received.lower()):
        raise InitDataError("подпись не совпадает")

    try:
        auth_date = int(data.get("auth_date", "0"))
    except ValueError as exc:
        raise InitDataError("некорректный auth_date") from exc
    now = time.time() if now is None else now
    if auth_date > 10**11:  # на случай миллисекунд
        auth_date //= 1000
    if not auth_date or now - auth_date > ttl_seconds:
        raise InitDataError("initData устарели")

    try:
        user = json.loads(data.get("user", ""))
        return WebAppUser(
            id=int(user["id"]),
            first_name=str(user.get("first_name") or ""),
            last_name=str(user.get("last_name") or ""),
            username=str(user.get("username") or ""),
        )
    except (ValueError, KeyError, TypeError) as exc:
        raise InitDataError("нет данных пользователя") from exc


def _login_key(bot_token: str) -> bytes:
    return hmac.new(b"LoginLink", bot_token.encode(), hashlib.sha256).digest()


def issue_login_token(user_id: int, name: str, bot_token: str, ttl_seconds: int, now: float | None = None) -> str:
    now = time.time() if now is None else now
    payload = json.dumps({"id": user_id, "name": name[:100], "exp": int(now + ttl_seconds)},
                         ensure_ascii=False, separators=(",", ":")).encode()
    body = base64.urlsafe_b64encode(payload).rstrip(b"=").decode()
    signature = hmac.new(_login_key(bot_token), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{signature}"


def validate_login_token(token: str, bot_token: str, now: float | None = None) -> WebAppUser:
    body, _, signature = token.strip().partition(".")
    expected = hmac.new(_login_key(bot_token), body.encode(), hashlib.sha256).hexdigest()
    if not body or not hmac.compare_digest(expected, signature):
        raise InitDataError("подпись токена не совпадает")
    try:
        data = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        user = WebAppUser(id=int(data["id"]), first_name=str(data.get("name") or ""))
        expires = int(data["exp"])
    except (ValueError, KeyError, TypeError) as exc:
        raise InitDataError("некорректный токен") from exc
    if (time.time() if now is None else now) > expires:
        raise InitDataError("токен устарел")
    return user


async def current_user(
    request: Request,
    x_init_data: str | None = Header(default=None),
    x_login_token: str | None = Header(default=None),
) -> WebAppUser:
    settings = request.app.state.settings
    try:
        if x_init_data:
            return validate_init_data(x_init_data, settings.bot_token, settings.init_data_ttl_seconds)
        if x_login_token:
            return validate_login_token(x_login_token, settings.bot_token)
        raise InitDataError("нет ни initData, ни токена входа")
    except InitDataError as exc:
        # Только имена полей, без значений: помогает разобраться с форматом, не раскрывая данные.
        fields = sorted(k for k, _ in parse_qsl(_normalize(x_init_data or ""), keep_blank_values=True))
        log.warning("Вход в мини-приложение отклонён: %s; поля initData: %s", exc, fields)
        raise HTTPException(
            status_code=401,
            detail={
                "code": "unauthorized",
                "message": "Ссылка устарела. Откройте приложение заново из чата с ботом.",
            },
        ) from exc
