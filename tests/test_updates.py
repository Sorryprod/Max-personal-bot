from app.max.updates import parse_update
from app.messaging import EventKind


def _message(text=None, attachments=None, mid="mid-1"):
    return {
        "update_type": "message_created",
        "timestamp": 1,
        "message": {
            "sender": {"user_id": 42, "first_name": "Анна", "is_bot": False},
            "recipient": {"chat_id": 7, "chat_type": "dialog"},
            "timestamp": 1,
            "body": {"mid": mid, "seq": 1, "text": text, "attachments": attachments or []},
        },
    }


def test_bot_started_with_payload():
    event = parse_update(
        {"update_type": "bot_started", "timestamp": 5, "chat_id": 7,
         "user": {"user_id": 42, "first_name": "Анна"}, "payload": "abc123"}
    )
    assert event.kind == EventKind.start
    assert event.payload == "abc123"
    assert event.key == "bot_started:42:5"


def test_start_command_with_payload():
    event = parse_update(_message("/start abc123"))
    assert event.kind == EventKind.start and event.payload == "abc123"


def test_text_message_key_is_mid():
    event = parse_update(_message("привет", mid="m-9"))
    assert event.kind == EventKind.text and event.key == "msg:m-9"


def test_contact_attachment():
    vcf = "BEGIN:VCARD\r\nVERSION:3.0\r\nTEL;TYPE=cell:79991234567\r\nEND:VCARD"
    event = parse_update(_message(attachments=[{"type": "contact", "payload": {"vcf_info": vcf}}]))
    assert event.kind == EventKind.contact and event.phone == "79991234567"


def test_callback():
    event = parse_update(
        {"update_type": "message_callback", "timestamp": 1,
         "callback": {"callback_id": "cb1", "payload": "role:employer", "timestamp": 1,
                      "user": {"user_id": 42, "first_name": "Анна"}},
         "message": _message("x")["message"]}
    )
    assert event.kind == EventKind.callback and event.payload == "role:employer"


def test_ignores_bots_and_group_chats():
    msg = _message("x")
    msg["message"]["sender"]["is_bot"] = True
    assert parse_update(msg) is None
    msg = _message("x")
    msg["message"]["recipient"]["chat_type"] = "chat"
    assert parse_update(msg) is None
    assert parse_update({"update_type": "dialog_muted"}) is None


async def test_duplicate_update_processed_once(dispatcher, messenger):
    event = parse_update(_message("/start"))
    await dispatcher.handle(event)
    await dispatcher.handle(event)
    assert len(messenger.sent) == 1


async def test_handler_error_is_reported_without_traceback(dispatcher, messenger, monkeypatch):
    async def boom(ctx):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.bot.router.common.fallback", boom)
    await dispatcher.handle(parse_update(_message("что-то")))
    assert len(messenger.sent) == 1
    assert "boom" not in messenger.sent[0].text
