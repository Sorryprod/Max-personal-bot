"""Кнопки входа в мини-приложение: нативно через MAX или запасной ссылкой с токеном."""

from urllib.parse import quote

from app.api.auth import issue_login_token
from app.config import Settings
from app.messaging import Button, ButtonKind, Messenger


class AppLinks:
    def __init__(self, settings: Settings, messenger: Messenger) -> None:
        self._settings = settings
        self._messenger = messenger

    def button(self, label: str, user_id: int, user_name: str, start_param: str = "") -> Button:
        if self._settings.webapp_open_mode == "link":
            token = issue_login_token(
                user_id, user_name, self._settings.bot_token, self._settings.login_link_ttl_seconds
            )
            query = f"?start={quote(start_param)}" if start_param else ""
            # Токен во фрагменте (#) не уходит на сервер в URL и не попадает в логи прокси.
            return Button(label, f"{self._settings.public_url}/app/{query}#login={token}", ButtonKind.link)
        if start_param:
            return Button(label, self._messenger.app_link(start_param), ButtonKind.link)
        return Button(label, kind=ButtonKind.app)
