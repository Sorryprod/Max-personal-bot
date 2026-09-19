import time
from urllib.parse import urlparse

import pytest

from app.api.auth import InitDataError, issue_login_token, validate_login_token
from app.bot.router import Dispatcher
from app.config import Settings
from app.messaging import ButtonKind
from app.services.applinks import AppLinks
from tests.helpers import buttons, press, text

TOKEN = "test-token"


def test_login_token_roundtrip():
    user = validate_login_token(issue_login_token(7, "Иван", TOKEN, 3600), TOKEN)
    assert user.id == 7 and user.full_name == "Иван"


def test_login_token_other_bot_rejected():
    with pytest.raises(InitDataError):
        validate_login_token(issue_login_token(7, "Иван", "other", 3600), TOKEN)


def test_login_token_tampered_rejected():
    token = issue_login_token(7, "Иван", TOKEN, 3600)
    body, sig = token.split(".")
    forged = issue_login_token(8, "Иван", "other", 3600).split(".")[0] + "." + sig
    with pytest.raises(InitDataError):
        validate_login_token(forged, TOKEN)


def test_login_token_expired():
    token = issue_login_token(7, "Иван", TOKEN, 60, now=time.time() - 120)
    with pytest.raises(InitDataError):
        validate_login_token(token, TOKEN)


async def test_api_accepts_login_token(api):
    resp = await api.get("/api/me", headers={"X-Login-Token": issue_login_token(7, "Иван", TOKEN, 3600)})
    assert resp.status_code == 200 and resp.json()["user"]["id"] == 7
    resp = await api.get("/api/me", headers={"X-Login-Token": "garbage.abc"})
    assert resp.status_code == 401


def test_native_mode_buttons(links):
    assert links.button("Кабинет", 1, "Иван").kind == ButtonKind.app
    create = links.button("Создать", 1, "Иван", "new")
    assert create.kind == ButtonKind.link and create.payload.endswith("?startapp=new")


def test_link_mode_requires_public_url():
    with pytest.raises(ValueError):
        Settings(bot_token=TOKEN, webapp_open_mode="link", _env_file=None)


async def test_link_mode_menu_opens_signed_page(session_factory, messenger):
    settings = Settings(bot_token=TOKEN, webapp_open_mode="link", public_url="https://demo.example.ru/",
                        _env_file=None)
    dispatcher = Dispatcher(session_factory, messenger, AppLinks(settings, messenger))
    await dispatcher.handle(press(10, "role:employer", name="Иван"))
    await dispatcher.handle(text(10, "Кафе", name="Иван"))
    await dispatcher.handle(text(10, "Белгород", name="Иван"))

    create = next(b for b in buttons(messenger.sent[-1]) if "Создать" in b.text)
    assert create.kind == ButtonKind.link
    url = urlparse(create.payload)
    assert (url.scheme, url.netloc, url.path, url.query) == ("https", "demo.example.ru", "/app/", "start=new")
    token = url.fragment.removeprefix("login=")
    assert validate_login_token(token, TOKEN).id == 10
