from app.bot.states import Ctx


async def start(ctx: Ctx) -> None:
    ctx.reply("Чтобы откликнуться, перейдите по ссылке-приглашению на вакансию.")


async def open_invite(ctx: Ctx, slug: str) -> None:
    ctx.reply("Раздел для соискателя скоро заработает.")


async def on_callback(ctx: Ctx, payload: str) -> None:
    ctx.reply("Раздел для соискателя скоро заработает.")


async def on_message(ctx: Ctx) -> None:
    ctx.reply("Раздел для соискателя скоро заработает.")
