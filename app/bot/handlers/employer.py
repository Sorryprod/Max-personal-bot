"""Сценарий работодателя в чате: название точки, город, меню с мини-приложением."""

from html import escape

from sqlalchemy import func, select

from app.bot import texts
from app.bot.states import Ctx, Step
from app.db import seed
from app.db.models import Employer, Vacancy
from app.messaging import Button, CallbackAnswer, Keyboard
from app.services import vacancies

TEXT_MIN, TEXT_MAX = 2, 100


def _clean(raw: str | None) -> str | None:
    value = " ".join((raw or "").split())
    return value if TEXT_MIN <= len(value) <= TEXT_MAX else None


def menu_keyboard(ctx: Ctx, show_example: bool = False) -> Keyboard:
    keyboard = [
        [ctx.app_button(texts.EMP_CREATE_BUTTON, "new")],
        [ctx.app_button(texts.EMP_CABINET_BUTTON)],
    ]
    if show_example:
        keyboard.append([Button(texts.EMP_EXAMPLE_BUTTON, "emp:example")])
    keyboard.append([Button(texts.EMP_EDIT_BUTTON, "emp:edit")])
    return keyboard


def _city_keyboard() -> Keyboard:
    buttons = [Button(city, f"emp:city:{i}") for i, city in enumerate(vacancies.BELGOROD_CITIES)]
    return [buttons[i : i + 2] for i in range(0, len(buttons), 2)]


async def _vacancy_count(ctx: Ctx, employer: Employer) -> int:
    return await ctx.session.scalar(select(func.count(Vacancy.id)).where(Vacancy.employer_id == employer.id)) or 0


async def start(ctx: Ctx) -> None:
    employer = await vacancies.get_employer(ctx.session, ctx.user_id)
    if employer and employer.place_name and employer.city:
        await _show_menu(ctx, employer)
        return
    _ask_place(ctx)


def _ask_place(ctx: Ctx) -> None:
    ctx.set_step(Step.emp_place)
    ctx.reply(texts.EMP_ASK_PLACE)


async def _show_menu(ctx: Ctx, employer: Employer) -> None:
    ctx.set_step(Step.idle)
    # Пока вакансий нет, предлагаем посмотреть работу с кандидатами на синтетическом примере.
    show_example = await _vacancy_count(ctx, employer) == 0
    ctx.reply(
        texts.EMP_MENU.format(place=escape(employer.place_name), city=escape(employer.city)),
        menu_keyboard(ctx, show_example),
    )


async def on_callback(ctx: Ctx, data: str) -> None:
    action, _, arg = data.partition(":")
    if action == "edit":
        _ask_place(ctx)
    elif action == "city" and ctx.state.step == Step.emp_city and arg.isdigit() \
            and int(arg) < len(vacancies.BELGOROD_CITIES):
        await _save(ctx, vacancies.BELGOROD_CITIES[int(arg)])
    elif action == "example":
        await _create_example(ctx)
    else:
        ctx.answer = CallbackAnswer(ctx.event.callback_id or "", notification=texts.STALE_BUTTON)


async def on_message(ctx: Ctx) -> None:
    step = ctx.state.step
    if step == Step.emp_place:
        place = _clean(ctx.event.text)
        if place is None:
            ctx.reply(texts.EMP_BAD_TEXT)
            return
        ctx.set_step(Step.emp_city, place_name=place)
        ctx.reply(texts.EMP_ASK_CITY, _city_keyboard())
    elif step == Step.emp_city:
        city = _clean(ctx.event.text)
        if city is None:
            ctx.reply(texts.EMP_BAD_TEXT, _city_keyboard())
            return
        await _save(ctx, city)
    else:
        ctx.reply(texts.FALLBACK)


async def _save(ctx: Ctx, city: str) -> None:
    place = (ctx.state.context or {}).get("place_name")
    if not place:  # контекст потерян — начинаем регистрацию заново
        _ask_place(ctx)
        return
    employer = await vacancies.upsert_employer(ctx.session, ctx.user_id, ctx.event.user_name, place, city)
    await _show_menu(ctx, employer)


async def _create_example(ctx: Ctx) -> None:
    employer = await vacancies.get_employer(ctx.session, ctx.user_id)
    if employer is None or not employer.place_name:
        _ask_place(ctx)
        return
    if await _vacancy_count(ctx, employer) > 0:  # повторное нажатие старой кнопки
        ctx.answer = CallbackAnswer(ctx.event.callback_id or "", notification=texts.STALE_BUTTON)
        return
    vacancy = await seed.create_example(ctx.session, employer)
    ctx.reply(
        texts.EMP_EXAMPLE_CREATED.format(position=escape(vacancy.position)),
        [[ctx.app_button(texts.EMP_CABINET_BUTTON, f"vacancy-{vacancy.id}")]],
    )
