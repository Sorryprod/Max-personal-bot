from typing import Any

from app.messaging import ButtonKind, Keyboard

# Ограничения MAX: до 30 рядов, до 7 кнопок в ряду (до 3 для link/open_app/request_contact).
MAX_ROWS = 30
MAX_PER_ROW = 7
MAX_PER_ROW_SPECIAL = 3
CALLBACK_PAYLOAD_LIMIT = 1024


def _button(btn: Any, bot_username: str) -> dict[str, Any]:
    match btn.kind:
        case ButtonKind.callback:
            return {"type": "callback", "text": btn.text, "payload": btn.payload[:CALLBACK_PAYLOAD_LIMIT]}
        case ButtonKind.link:
            return {"type": "link", "text": btn.text, "url": btn.payload}
        case ButtonKind.contact:
            return {"type": "request_contact", "text": btn.text}
        case ButtonKind.app:
            # Поддержка payload у open_app в документации не описана — не передаём,
            # чтобы неизвестное поле не сломало отправку всего сообщения.
            return {"type": "open_app", "text": btn.text, "web_app": bot_username}
    raise ValueError(f"Неизвестный тип кнопки: {btn.kind}")


def to_max_attachments(keyboard: Keyboard | None, bot_username: str) -> list[dict[str, Any]]:
    if not keyboard:
        return []
    rows = []
    for row in keyboard[:MAX_ROWS]:
        special = any(b.kind != ButtonKind.callback for b in row)
        limit = MAX_PER_ROW_SPECIAL if special else MAX_PER_ROW
        rows.append([_button(b, bot_username) for b in row[:limit]])
    return [{"type": "inline_keyboard", "payload": {"buttons": rows}}]
