import os

# Переменные окружения важнее .env — тесты не зависят от локальных настроек.
os.environ["BOT_TOKEN"] = "test-token"
os.environ["UPDATES_MODE"] = "polling"

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from app.bot.router import Dispatcher
from app.db.models import Base
from app.db.session import make_session_factory
from app.messaging import CallbackAnswer, OutMessage


class FakeMessenger:
    bot_username = "test_bot"

    def __init__(self) -> None:
        self.sent: list[OutMessage] = []
        self.answers: list[CallbackAnswer] = []

    async def send(self, message: OutMessage) -> bool:
        self.sent.append(message)
        return True

    async def answer_callback(self, answer: CallbackAnswer) -> bool:
        self.answers.append(answer)
        return True

    def invite_link(self, slug: str) -> str:
        return f"https://max.ru/{self.bot_username}?start={slug}"

    def app_link(self, start_param: str) -> str:
        return f"https://max.ru/{self.bot_username}?startapp={start_param}"


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield make_session_factory(engine)
    await engine.dispose()


@pytest.fixture
def messenger() -> FakeMessenger:
    return FakeMessenger()


@pytest.fixture
def settings():
    from app.config import Settings

    return Settings(bot_token="test-token", _env_file=None)


@pytest.fixture
def links(settings, messenger):
    from app.services.applinks import AppLinks

    return AppLinks(settings, messenger)


@pytest.fixture
def dispatcher(session_factory, messenger, links) -> Dispatcher:
    return Dispatcher(session_factory, messenger, links)


@pytest.fixture
async def api(session_factory, messenger, settings, links):
    """HTTP-клиент к API без lifespan: БД и мессенджер подменены."""
    import httpx

    from app.main import create_app

    app = create_app(settings)
    app.state.session_factory = session_factory
    app.state.messenger = messenger
    app.state.links = links
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client
