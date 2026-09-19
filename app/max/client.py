"""Тонкий адаптер над MAX Bot API — единственное место, знающее формат запросов платформы."""

import asyncio
import logging
import ssl
from pathlib import Path
from typing import Any

import certifi
import httpx

from app.max.keyboards import to_max_attachments
from app.messaging import CallbackAnswer, OutMessage

log = logging.getLogger(__name__)

RETRY_STATUSES = {429, 500, 502, 503, 504}


class MaxApiError(Exception):
    pass


def _ssl_context(extra_ca_file: Path | None) -> ssl.SSLContext:
    ctx = ssl.create_default_context(cafile=certifi.where())
    if extra_ca_file and extra_ca_file.exists():
        ctx.load_verify_locations(cafile=str(extra_ca_file))
    return ctx


class MaxClient:
    def __init__(
        self,
        token: str,
        base_url: str,
        timeout: float = 10.0,
        extra_ca_file: Path | None = None,
        retries: int = 3,
        bot_username: str = "",
    ) -> None:
        self._http = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": token},
            timeout=timeout,
            verify=_ssl_context(extra_ca_file),
        )
        self._retries = retries
        self.bot_username = bot_username

    async def aclose(self) -> None:
        await self._http.aclose()

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self._retries):
            try:
                resp = await self._http.request(
                    method,
                    path,
                    params=params,
                    json=json,
                    timeout=timeout if timeout is not None else httpx.USE_CLIENT_DEFAULT,
                )
            except httpx.TransportError as exc:
                last_error = exc
            else:
                if resp.status_code < 400:
                    return resp.json() if resp.content else {}
                last_error = MaxApiError(f"{method} {path} -> {resp.status_code}: {resp.text[:300]}")
                if resp.status_code not in RETRY_STATUSES:
                    break
            await asyncio.sleep(0.5 * 2**attempt)
        raise MaxApiError(str(last_error)) from last_error

    # --- методы API ---

    async def get_me(self) -> dict[str, Any]:
        return await self.request("GET", "/me")

    async def get_updates(self, marker: int | None, timeout: int = 30) -> dict[str, Any]:
        params: dict[str, Any] = {"timeout": timeout, "limit": 100}
        if marker is not None:
            params["marker"] = marker
        # HTTP-таймаут должен быть больше серверного long-poll таймаута.
        return await self.request("GET", "/updates", params=params, timeout=timeout + 15)

    async def subscribe(self, url: str, secret: str, update_types: list[str]) -> None:
        await self.request(
            "POST", "/subscriptions", json={"url": url, "secret": secret, "update_types": update_types}
        )

    async def set_commands(self, commands: list[tuple[str, str]]) -> None:
        body = {"commands": [{"name": name, "description": description} for name, description in commands]}
        try:
            await self.request("PATCH", "/me/commands", json=body)
        except MaxApiError:
            # Документация называет /me/commands, официальная библиотека шлёт commands в PATCH /me.
            await self.request("PATCH", "/me", json=body)

    async def list_subscriptions(self) -> list[dict[str, Any]]:
        data = await self.request("GET", "/subscriptions")
        return data.get("subscriptions", [])

    async def unsubscribe(self, url: str) -> None:
        await self.request("DELETE", "/subscriptions", params={"url": url})

    # --- реализация app.messaging.Messenger: ошибки не пробрасываются наружу ---

    async def send(self, message: OutMessage) -> bool:
        if message.user_id <= 0:
            # id в MAX положительные; отрицательные — у синтетических демо-пользователей из seed.
            log.info("Сообщение демо-пользователю %s не отправляется", message.user_id)
            return False
        body: dict[str, Any] = {"text": message.text, "format": "html"}
        attachments = to_max_attachments(message.keyboard, self.bot_username)
        if attachments:
            body["attachments"] = attachments
        try:
            await self.request("POST", "/messages", params={"user_id": message.user_id}, json=body)
            return True
        except MaxApiError:
            log.exception("Не удалось отправить сообщение пользователю %s", message.user_id)
            return False

    async def answer_callback(self, answer: CallbackAnswer) -> bool:
        body: dict[str, Any] = {}
        if answer.notification:
            body["notification"] = answer.notification
        if answer.edit_text is not None:
            # Пустой список вложений убирает клавиатуру с исходного сообщения.
            body["message"] = {"text": answer.edit_text, "format": "html", "attachments": []}
        if not body:
            return True  # MAX требует message или notification — отвечать нечем
        try:
            await self.request("POST", "/answers", params={"callback_id": answer.callback_id}, json=body)
            return True
        except MaxApiError:
            log.warning("Не удалось ответить на callback %s", answer.callback_id, exc_info=True)
            return False

    def invite_link(self, slug: str) -> str:
        return f"https://max.ru/{self.bot_username}?start={slug}"

    def app_link(self, start_param: str) -> str:
        return f"https://max.ru/{self.bot_username}?startapp={start_param}"
