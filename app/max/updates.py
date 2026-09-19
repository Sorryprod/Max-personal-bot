"""Перевод сырых апдейтов MAX во внутренние IncomingEvent."""

import re
from typing import Any

from app.messaging import EventKind, IncomingEvent

UPDATE_TYPES = ["bot_started", "message_created", "message_callback"]

_TEL_RE = re.compile(r"^TEL[^:]*:(.+)$", re.MULTILINE)


def _user_name(user: dict[str, Any]) -> str:
    parts = [user.get("first_name") or "", user.get("last_name") or ""]
    return " ".join(p for p in parts if p).strip() or user.get("name") or ""


def _phone_from_contact(attachments: list[dict[str, Any]]) -> str | None:
    for att in attachments:
        if att.get("type") != "contact":
            continue
        vcf = (att.get("payload") or {}).get("vcf_info") or ""
        match = _TEL_RE.search(vcf)
        if match:
            return match.group(1).strip()
    return None


def _pressed_button_text(message: dict[str, Any], payload: str) -> str:
    for att in (message.get("body") or {}).get("attachments") or []:
        if att.get("type") != "inline_keyboard":
            continue
        for row in (att.get("payload") or {}).get("buttons") or []:
            for button in row:
                if button.get("payload") == payload:
                    return button.get("text") or ""
    return ""


def parse_update(raw: dict[str, Any]) -> IncomingEvent | None:
    """Возвращает событие или None, если апдейт нас не интересует."""
    utype = raw.get("update_type")

    if utype == "bot_started":
        user = raw.get("user") or {}
        if "user_id" not in user:
            return None
        return IncomingEvent(
            key=f"bot_started:{user['user_id']}:{raw.get('timestamp')}",
            kind=EventKind.start,
            user_id=user["user_id"],
            user_name=_user_name(user),
            payload=raw.get("payload") or None,
        )

    if utype == "message_created":
        message = raw.get("message") or {}
        sender = message.get("sender") or {}
        body = message.get("body") or {}
        recipient = message.get("recipient") or {}
        if sender.get("is_bot") or "user_id" not in sender or not body.get("mid"):
            return None
        # Бот работает только в личном диалоге.
        if recipient.get("chat_type") not in (None, "dialog"):
            return None
        common = {
            "key": f"msg:{body['mid']}",
            "user_id": sender["user_id"],
            "user_name": _user_name(sender),
        }
        phone = _phone_from_contact(body.get("attachments") or [])
        if phone:
            return IncomingEvent(kind=EventKind.contact, phone=phone, **common)
        text = (body.get("text") or "").strip()
        if text == "/start" or text.startswith("/start "):
            payload = text[len("/start") :].strip() or None
            return IncomingEvent(kind=EventKind.start, payload=payload, **common)
        return IncomingEvent(kind=EventKind.text, text=text, **common)

    if utype == "message_callback":
        callback = raw.get("callback") or {}
        user = callback.get("user") or {}
        if not callback.get("callback_id") or "user_id" not in user:
            return None
        message = raw.get("message") or {}
        payload = callback.get("payload") or ""
        return IncomingEvent(
            key=f"cb:{callback['callback_id']}",
            kind=EventKind.callback,
            user_id=user["user_id"],
            user_name=_user_name(user),
            payload=payload,
            callback_id=callback["callback_id"],
            source_text=(message.get("body") or {}).get("text") or "",
            pressed_text=_pressed_button_text(message, payload),
        )

    return None
