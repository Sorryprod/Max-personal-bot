"""Приём событий: идемпотентность, транзакция, маршрутизация по состоянию диалога."""

import logging
from html import escape

from sqlalchemy import insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot import texts
from app.bot.handlers import candidate, common, employer
from app.bot.states import Ctx, load_state
from app.db.models import ProcessedUpdate
from app.messaging import CallbackAnswer, EventKind, IncomingEvent, Messenger, Outbox, flush_outbox

log = logging.getLogger(__name__)


async def mark_processed(session: AsyncSession, key: str) -> bool:
    """Помечает апдейт обработанным. False — если он уже был обработан (повторная доставка)."""
    dialect = session.bind.dialect.name
    table = ProcessedUpdate.__table__
    if dialect == "postgresql":
        stmt = pg_insert(table).values(update_key=key).on_conflict_do_nothing()
    elif dialect == "sqlite":
        stmt = sqlite_insert(table).values(update_key=key).on_conflict_do_nothing()
    else:
        stmt = insert(table).values(update_key=key)
    result = await session.execute(stmt)
    return result.rowcount == 1


def default_callback_answer(event: IncomingEvent) -> CallbackAnswer:
    """По умолчанию убираем клавиатуру и оставляем под сообщением выбранный вариант."""
    if event.source_text and event.pressed_text:
        return CallbackAnswer(
            event.callback_id or "",
            edit_text=f"{escape(event.source_text)}\n\n<b>✓ {escape(event.pressed_text)}</b>",
        )
    return CallbackAnswer(event.callback_id or "", notification="Принято")


async def route(ctx: Ctx) -> None:
    event = ctx.event
    if event.kind == EventKind.callback:
        ctx.answer = default_callback_answer(event)
        await _route_callback(ctx)
        if ctx.answer is not None:
            ctx.outbox.callback_answers.append(ctx.answer)
        return

    if event.kind == EventKind.start:
        if event.payload:
            await candidate.open_invite(ctx, event.payload)
        else:
            await common.greet(ctx)
        return

    step = ctx.state.step
    if step.startswith("emp_"):
        await employer.on_message(ctx)
    elif step.startswith("cand_"):
        await candidate.on_message(ctx)
    else:
        await common.fallback(ctx)


async def _route_callback(ctx: Ctx) -> None:
    payload = ctx.event.payload or ""
    prefix, _, rest = payload.partition(":")
    if prefix == "role":
        await common.choose_role(ctx, rest)
    elif prefix == "emp":
        await employer.on_callback(ctx, rest)
    elif prefix == "cand":
        await candidate.on_callback(ctx, rest)
    else:
        ctx.reply(texts.UNKNOWN_BUTTON)


class Dispatcher:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], messenger: Messenger) -> None:
        self._sf = session_factory
        self._messenger = messenger

    async def handle(self, event: IncomingEvent) -> None:
        log.info("Событие %s от %s, payload=%r", event.kind, event.user_id, event.payload)
        outbox = Outbox()
        try:
            async with self._sf() as session, session.begin():
                if not await mark_processed(session, event.key):
                    log.info("Повторная доставка %s — пропускаем", event.key)
                    return
                state = await load_state(session, event.user_id)
                await route(Ctx(session, event, state, outbox, self._messenger))
        except (OperationalError, InterfaceError, OSError):
            raise  # БД недоступна — пусть платформа доставит апдейт повторно
        except Exception as exc:  # noqa: BLE001 — пользователь не должен видеть трейсбек
            await self._recover(event, exc)
            return
        await flush_outbox(self._messenger, outbox)

    async def _recover(self, event: IncomingEvent, exc: Exception) -> None:
        """Ошибка в обработчике: транзакция откачена, шаг диалога не сдвинулся — можно повторить."""
        log.exception("Ошибка обработки %s", event.key, exc_info=exc)
        outbox = Outbox()
        if event.callback_id:
            outbox.callback_answers.append(
                CallbackAnswer(event.callback_id, notification="Ошибка, попробуйте ещё раз")
            )
        outbox.send(event.user_id, texts.INTERNAL_ERROR)
        try:
            async with self._sf() as session, session.begin():
                await mark_processed(session, event.key)
        except Exception:  # noqa: BLE001
            log.exception("Не удалось пометить апдейт %s обработанным", event.key)
        await flush_outbox(self._messenger, outbox)
