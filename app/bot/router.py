"""Приём событий: идемпотентность, транзакция, маршрутизация по состоянию диалога."""

import logging

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


async def route(ctx: Ctx) -> None:
    event = ctx.event
    if event.kind == EventKind.callback:
        ctx.outbox.callback_answers.append(CallbackAnswer(event.callback_id or ""))
        payload = event.payload or ""
        prefix = payload.split(":", 1)[0]
        if prefix == "role":
            await common.choose_role(ctx, payload.split(":", 1)[1] if ":" in payload else "")
        elif prefix == "emp":
            await employer.on_callback(ctx, payload)
        elif prefix == "cand":
            await candidate.on_callback(ctx, payload)
        else:
            ctx.reply(texts.UNKNOWN_BUTTON)
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


class Dispatcher:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], messenger: Messenger) -> None:
        self._sf = session_factory
        self._messenger = messenger

    async def handle(self, event: IncomingEvent) -> None:
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
            outbox.callback_answers.append(CallbackAnswer(event.callback_id))
        outbox.send(event.user_id, texts.INTERNAL_ERROR)
        try:
            async with self._sf() as session, session.begin():
                await mark_processed(session, event.key)
        except Exception:  # noqa: BLE001
            log.exception("Не удалось пометить апдейт %s обработанным", event.key)
        await flush_outbox(self._messenger, outbox)
