"""Платформонезависимые типы входящих событий и исходящих сообщений.

Бизнес-логика работает только с этими типами; перевод в формат MAX и обратно
живёт в app/max/.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class EventKind(StrEnum):
    start = "start"  # первый запуск бота или /start, возможно с payload из ссылки
    text = "text"
    callback = "callback"  # нажатие inline-кнопки
    contact = "contact"  # пользователь поделился номером телефона


@dataclass(frozen=True)
class IncomingEvent:
    key: str  # ключ идемпотентности
    kind: EventKind
    user_id: int
    user_name: str = ""
    text: str | None = None
    payload: str | None = None
    callback_id: str | None = None
    phone: str | None = None
    # Для callback: текст сообщения с кнопками и подпись нажатой кнопки.
    source_text: str = ""
    pressed_text: str = ""


class ButtonKind(StrEnum):
    callback = "callback"
    link = "link"
    contact = "contact"  # запросить номер телефона
    app = "app"  # открыть мини-приложение бота


@dataclass(frozen=True)
class Button:
    text: str
    payload: str = ""  # данные callback или URL для link
    kind: ButtonKind = ButtonKind.callback


Keyboard = list[list[Button]]


@dataclass
class OutMessage:
    user_id: int
    text: str  # HTML: <b>, <i>, <a>; пользовательский ввод экранируется
    keyboard: Keyboard | None = None


@dataclass
class CallbackAnswer:
    """Ответ на нажатие кнопки: всплывающее уведомление и/или замена исходного сообщения.

    edit_text задан — исходное сообщение заменяется этим текстом без клавиатуры.
    """

    callback_id: str
    notification: str | None = None
    edit_text: str | None = None


@dataclass
class Outbox:
    """Сообщения копятся во время обработки и отправляются после коммита транзакции."""

    messages: list[OutMessage] = field(default_factory=list)
    callback_answers: list[CallbackAnswer] = field(default_factory=list)

    def send(self, user_id: int, text: str, keyboard: Keyboard | None = None) -> None:
        self.messages.append(OutMessage(user_id, text, keyboard))


class Messenger(Protocol):
    bot_username: str

    async def send(self, message: OutMessage) -> bool: ...

    async def answer_callback(self, answer: CallbackAnswer) -> bool: ...

    def invite_link(self, slug: str) -> str: ...


async def flush_outbox(messenger: Messenger, outbox: Outbox) -> None:
    for answer in outbox.callback_answers:
        await messenger.answer_callback(answer)
    for message in outbox.messages:
        await messenger.send(message)
