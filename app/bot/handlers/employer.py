from app.bot.states import Ctx


async def start(ctx: Ctx) -> None:
    ctx.reply("Раздел для работодателя скоро заработает.")


async def on_callback(ctx: Ctx, payload: str) -> None:
    ctx.reply("Раздел для работодателя скоро заработает.")


async def on_message(ctx: Ctx) -> None:
    ctx.reply("Раздел для работодателя скоро заработает.")
