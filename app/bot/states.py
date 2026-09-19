"""Конечный автомат диалога. Состояние хранится в БД, а не в памяти процесса."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DialogState
from app.messaging import CallbackAnswer, IncomingEvent, Keyboard, Messenger, Outbox
from app.services.applinks import AppLinks


class Step(StrEnum):
    idle = "idle"
    # соискатель (префикс cand_ — маршрутизация в handlers/candidate.py)
    cand_question = "cand_question"
    cand_name = "cand_name"
    cand_contact = "cand_contact"
    cand_confirm = "cand_confirm"
    # работодатель (префикс emp_)
    emp_place = "emp_place"
    emp_city = "emp_city"


async def load_state(session: AsyncSession, user_id: int) -> DialogState:
    # FOR UPDATE сериализует параллельные апдейты одного пользователя.
    state = await session.scalar(
        select(DialogState).where(DialogState.max_user_id == user_id).with_for_update()
    )
    if state is None:
        state = DialogState(max_user_id=user_id, step=Step.idle, context={})
        session.add(state)
        await session.flush()
    return state


@dataclass
class Ctx:
    session: AsyncSession
    event: IncomingEvent
    state: DialogState
    outbox: Outbox
    messenger: Messenger
    links: AppLinks
    # Ответ на нажатие кнопки; обработчик может заменить или обнулить его.
    answer: CallbackAnswer | None = field(default=None)

    @property
    def user_id(self) -> int:
        return self.event.user_id

    def app_button(self, label: str, start_param: str = ""):
        return self.links.button(label, self.user_id, self.event.user_name, start_param)

    def reply(self, text: str, keyboard: Keyboard | None = None) -> None:
        self.outbox.send(self.user_id, text, keyboard)

    def set_step(self, step: str, **context: Any) -> None:
        self.state.step = step
        self.state.context = context

    def update_context(self, **values: Any) -> None:
        # Новый dict, чтобы SQLAlchemy заметил изменение JSON-поля.
        self.state.context = {**(self.state.context or {}), **values}
