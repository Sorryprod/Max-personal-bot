import os

os.environ.setdefault("BOT_TOKEN", "test-token")

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
def dispatcher(session_factory, messenger) -> Dispatcher:
    return Dispatcher(session_factory, messenger)
