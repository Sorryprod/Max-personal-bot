"""Команды про данные пользователя: /privacy и /delete (152-ФЗ)."""

from app.bot import texts
from app.bot.states import Ctx, Step
from app.messaging import Button, CallbackAnswer
from app.services import account


async def privacy(ctx: Ctx) -> None:
    ctx.set_step(Step.idle)
    ctx.reply(texts.PRIVACY)


async def ask_delete(ctx: Ctx) -> None:
    data = await account.user_data(ctx.session, ctx.user_id)
    ctx.set_step(Step.idle)
    if data.empty:
        ctx.reply(texts.DELETE_NOTHING)
        return
    parts = []
    if data.is_candidate:
        parts.append(texts.DELETE_PART_CANDIDATE.format(n=data.applications))
    if data.is_employer:
        parts.append(texts.DELETE_PART_EMPLOYER.format(n=data.vacancies))
    ctx.reply(
        texts.DELETE_CONFIRM.format(parts="\n".join(parts)),
        [[Button(texts.DELETE_YES, "acc:delete"), Button(texts.DELETE_NO, "acc:keep")]],
    )


async def on_callback(ctx: Ctx, data: str) -> None:
    if data == "delete":
        await account.delete_user_data(ctx.session, ctx.user_id)
        ctx.reply(texts.DELETE_DONE)
    elif data == "keep":
        ctx.reply(texts.DELETE_CANCELLED)
    else:
        ctx.answer = CallbackAnswer(ctx.event.callback_id or "", notification=texts.STALE_BUTTON)
