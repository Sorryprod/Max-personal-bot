import itertools

from app.messaging import EventKind, IncomingEvent

_seq = itertools.count()


def start(user_id: int, payload: str | None = None, name: str = "Анна Петрова") -> IncomingEvent:
    return IncomingEvent(key=f"s{next(_seq)}", kind=EventKind.start, user_id=user_id, user_name=name,
                         payload=payload)


def text(user_id: int, value: str, name: str = "Анна Петрова") -> IncomingEvent:
    return IncomingEvent(key=f"t{next(_seq)}", kind=EventKind.text, user_id=user_id, user_name=name, text=value)


def press(user_id: int, payload: str, name: str = "Анна Петрова") -> IncomingEvent:
    n = next(_seq)
    return IncomingEvent(key=f"c{n}", kind=EventKind.callback, user_id=user_id, user_name=name,
                         payload=payload, callback_id=f"cb{n}", source_text="вопрос", pressed_text="ответ")


def contact(user_id: int, phone: str, name: str = "Анна Петрова") -> IncomingEvent:
    return IncomingEvent(key=f"p{next(_seq)}", kind=EventKind.contact, user_id=user_id, user_name=name,
                         phone=phone)


def buttons(message) -> list:
    return [b for row in (message.keyboard or []) for b in row]
