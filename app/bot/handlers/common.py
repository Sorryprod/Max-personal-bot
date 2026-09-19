from app.bot import texts
from app.bot.states import Ctx, Step
from app.bot.handlers import candidate, employer
from app.messaging import Button


def role_keyboard() -> list[list[Button]]:
    return [
        [Button(texts.ROLE_EMPLOYER, "role:employer")],
        [Button(texts.ROLE_CANDIDATE, "role:candidate")],
    ]


async def greet(ctx: Ctx) -> None:
    ctx.set_step(Step.idle)
    ctx.reply(texts.GREETING, role_keyboard())


async def choose_role(ctx: Ctx, role: str) -> None:
    if role == "employer":
        await employer.start(ctx)
    elif role == "candidate":
        await candidate.start(ctx)
    else:
        await greet(ctx)


async def fallback(ctx: Ctx) -> None:
    ctx.reply(texts.FALLBACK, role_keyboard())
