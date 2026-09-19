"""Сценарий соискателя: ссылка-приглашение → карточка → вопросы → имя и контакт → отклик."""

from html import escape

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.bot import texts
from app.bot.states import Ctx, Step
from app.bot.views import vacancy_card
from app.db.models import Application, ApplicationStatus, Candidate, QuestionType, ScreeningQuestion, Vacancy
from app.messaging import Button, ButtonKind, CallbackAnswer, EventKind, Keyboard
from app.services import notifications, screening

# --- вход ---


async def start(ctx: Ctx) -> None:
    """Роль «Я ищу работу» без ссылки: показываем свои отклики или подсказку."""
    ctx.set_step(Step.idle)
    applications = await screening.candidate_applications(ctx.session, ctx.user_id)
    if not applications:
        ctx.reply(texts.CANDIDATE_NO_LINK)
        return
    lines = [texts.MY_APPLICATIONS_TITLE]
    for app in applications:
        status = screening.STATUS_LABELS.get(ApplicationStatus(app.status), app.status)
        place = app.vacancy.employer.place_name
        lines.append(f"• {escape(app.vacancy.position)}, {escape(place)} — <i>{escape(status)}</i>")
    ctx.reply("\n".join(lines))


async def open_invite(ctx: Ctx, slug: str) -> None:
    vacancy = await screening.get_vacancy_by_slug(ctx.session, slug)
    if not screening.is_open(vacancy):
        ctx.set_step(Step.idle)
        ctx.reply(texts.VACANCY_NOT_FOUND)
        return
    assert vacancy is not None
    candidate = await ctx.session.scalar(select(Candidate).where(Candidate.max_user_id == ctx.user_id))
    application = await screening.find_application(ctx.session, vacancy.id, candidate.id) if candidate else None

    if application and application.status != ApplicationStatus.new:
        ctx.set_step(Step.idle)
        status = screening.STATUS_LABELS.get(ApplicationStatus(application.status), application.status)
        ctx.reply(f"{vacancy_card(vacancy)}\n\n{texts.ALREADY_APPLIED.format(status=escape(status))}")
        return
    if application:  # анкета начата, но не закончена — продолжаем с того же места
        ctx.reply(f"{vacancy_card(vacancy)}\n\n{texts.RESUME_APPLICATION}")
        assert candidate is not None
        await _ask_next(ctx, vacancy, application, candidate)
        return
    ctx.set_step(Step.idle)
    ctx.reply(vacancy_card(vacancy), [[Button(texts.APPLY_BUTTON, f"cand:apply:{vacancy.id}")]])


# --- кнопки ---


async def on_callback(ctx: Ctx, data: str) -> None:
    action, _, arg = data.partition(":")
    if action == "apply" and arg.isdigit():
        await _apply(ctx, int(arg))
    elif action == "ans":
        qid, _, value = arg.partition(":")
        if not qid.isdigit() or not _awaiting_question(ctx, int(qid)):
            ctx.answer = CallbackAnswer(ctx.event.callback_id or "", notification=texts.STALE_BUTTON)
            return
        await _handle_answer(ctx, value)
    elif action == "name_profile" and ctx.state.step == Step.cand_name:
        await _set_name(ctx, ctx.event.user_name)
    elif action in ("confirm", "edit") and ctx.state.step == Step.cand_confirm:
        loaded = await _load(ctx)
        if loaded is None:
            return
        vacancy, application, candidate = loaded
        if action == "confirm":
            await _finish(ctx, vacancy, application, candidate)
        else:
            _ask_name(ctx, candidate)
    elif action == "my":
        await start(ctx)
    else:
        ctx.answer = CallbackAnswer(ctx.event.callback_id or "", notification=texts.STALE_BUTTON)


# --- текстовые сообщения и контакт ---


async def on_message(ctx: Ctx) -> None:
    event = ctx.event
    step = ctx.state.step
    if step == Step.cand_question:
        if event.kind != EventKind.text or not event.text:
            await _reask(ctx, texts.ANSWER_WITH_BUTTON)
            return
        await _handle_answer(ctx, event.text)
    elif step == Step.cand_name:
        await _set_name(ctx, event.text or "", from_user_input=True)
    elif step == Step.cand_contact:
        await _set_contact(ctx)
    elif step == Step.cand_confirm:
        ctx.reply(texts.CONFIRM_WITH_BUTTON, _confirm_keyboard())
    else:
        ctx.reply(texts.FALLBACK)


# --- шаги анкеты ---


async def _apply(ctx: Ctx, vacancy_id: int) -> None:
    vacancy = await screening.get_vacancy(ctx.session, vacancy_id)
    if not screening.is_open(vacancy):
        ctx.set_step(Step.idle)
        ctx.reply(texts.VACANCY_NOT_FOUND)
        return
    assert vacancy is not None
    candidate = await screening.get_or_create_candidate(ctx.session, ctx.user_id, ctx.event.user_name)
    application, _ = await screening.start_application(ctx.session, vacancy, candidate)
    if application.status != ApplicationStatus.new:
        status = screening.STATUS_LABELS.get(ApplicationStatus(application.status), application.status)
        ctx.reply(texts.ALREADY_APPLIED.format(status=escape(status)))
        return
    await _ask_next(ctx, vacancy, application, candidate)


async def _ask_next(ctx: Ctx, vacancy: Vacancy, application: Application, candidate: Candidate) -> None:
    question = screening.next_question(vacancy, application)
    base = {"vacancy_id": vacancy.id, "application_id": application.id}
    if question is not None:
        ctx.set_step(Step.cand_question, question_id=question.id, **base)
        _send_question(ctx, vacancy, question)
        return
    # Данные уже есть с прошлого отклика — предлагаем отправить без повторного ввода.
    if candidate.contact and screening.validate_name(candidate.name):
        ctx.set_step(Step.cand_confirm, **base)
        ctx.reply(
            texts.CONFIRM_DATA.format(name=escape(candidate.name), contact=escape(candidate.contact)),
            _confirm_keyboard(),
        )
        return
    ctx.set_step(Step.cand_name, **base)
    _ask_name(ctx, candidate)


def _send_question(ctx: Ctx, vacancy: Vacancy, question: ScreeningQuestion, prefix: str = "") -> None:
    number = vacancy.questions.index(question) + 1
    text = f"{prefix}<b>Вопрос {number} из {len(vacancy.questions)}</b>\n{escape(question.text)}"
    keyboard: Keyboard | None = None
    if question.qtype == QuestionType.yes_no:
        keyboard = [[
            Button("Да", f"cand:ans:{question.id}:{screening.YES}"),
            Button("Нет", f"cand:ans:{question.id}:{screening.NO}"),
        ]]
    elif question.qtype == QuestionType.choice:
        keyboard = [[Button(opt, f"cand:ans:{question.id}:{i}")] for i, opt in enumerate(question.options)]
    else:
        text += f"\n\n<i>{texts.ANSWER_WITH_TEXT}</i>"
    ctx.reply(text, keyboard)


def _awaiting_question(ctx: Ctx, question_id: int) -> bool:
    return ctx.state.step == Step.cand_question and (ctx.state.context or {}).get("question_id") == question_id


async def _load(ctx: Ctx) -> tuple[Vacancy, Application, Candidate] | None:
    """Достаёт вакансию и отклик из контекста диалога; если их больше нет — сбрасывает диалог."""
    context = ctx.state.context or {}
    vacancy = await screening.get_vacancy(ctx.session, context.get("vacancy_id", 0))
    application = await ctx.session.scalar(
        select(Application)
        .where(Application.id == context.get("application_id", 0))
        .options(selectinload(Application.answers), selectinload(Application.candidate))
    )
    if not screening.is_open(vacancy) or application is None:
        ctx.set_step(Step.idle)
        ctx.reply(texts.VACANCY_NOT_FOUND)
        return None
    assert vacancy is not None
    return vacancy, application, application.candidate


async def _reask(ctx: Ctx, hint: str) -> None:
    loaded = await _load(ctx)
    if loaded is None:
        return
    vacancy, application, _ = loaded
    question = next((q for q in vacancy.questions if q.id == ctx.state.context.get("question_id")), None)
    if question is None:
        await _ask_next(ctx, *loaded)
        return
    _send_question(ctx, vacancy, question, prefix=f"{hint}\n\n")


async def _handle_answer(ctx: Ctx, raw: str) -> None:
    loaded = await _load(ctx)
    if loaded is None:
        return
    vacancy, application, candidate = loaded
    question = next((q for q in vacancy.questions if q.id == ctx.state.context.get("question_id")), None)
    if question is None:  # вопрос удалили, пока кандидат отвечал
        await _ask_next(ctx, vacancy, application, candidate)
        return
    value = screening.normalize_answer(question, raw)
    if value is None:
        hint = texts.ANSWER_WITH_BUTTON if question.qtype != QuestionType.text else texts.ANSWER_EMPTY
        _send_question(ctx, vacancy, question, prefix=f"{hint}\n\n")
        return
    await screening.record_answer(ctx.session, application, question, value)
    await _ask_next(ctx, vacancy, application, candidate)


def _name_keyboard(ctx: Ctx) -> Keyboard | None:
    profile_name = screening.validate_name(ctx.event.user_name)
    return [[Button(f"Да, {profile_name}", "cand:name_profile")]] if profile_name else None


def _ask_name(ctx: Ctx, candidate: Candidate) -> None:
    ctx.set_step(Step.cand_name, **_base_context(ctx))
    ctx.reply(texts.ASK_NAME, _name_keyboard(ctx))


def _base_context(ctx: Ctx) -> dict[str, int]:
    context = ctx.state.context or {}
    return {"vacancy_id": context.get("vacancy_id", 0), "application_id": context.get("application_id", 0)}


async def _set_name(ctx: Ctx, raw: str, from_user_input: bool = False) -> None:
    name = screening.validate_name(raw)
    if name is None:
        ctx.reply(texts.BAD_NAME if from_user_input else texts.ASK_NAME, _name_keyboard(ctx))
        return
    loaded = await _load(ctx)
    if loaded is None:
        return
    _, _, candidate = loaded
    candidate.name = name
    ctx.set_step(Step.cand_contact, **_base_context(ctx))
    ctx.reply(texts.ASK_CONTACT, [[Button(texts.SHARE_CONTACT_BUTTON, kind=ButtonKind.contact)]])


async def _set_contact(ctx: Ctx) -> None:
    raw = ctx.event.phone if ctx.event.kind == EventKind.contact else ctx.event.text
    phone = screening.normalize_phone(raw or "")
    if phone is None:
        ctx.reply(texts.BAD_PHONE, [[Button(texts.SHARE_CONTACT_BUTTON, kind=ButtonKind.contact)]])
        return
    loaded = await _load(ctx)
    if loaded is None:
        return
    vacancy, application, candidate = loaded
    candidate.contact = phone
    await _finish(ctx, vacancy, application, candidate)


async def _finish(ctx: Ctx, vacancy: Vacancy, application: Application, candidate: Candidate) -> None:
    await screening.submit_application(ctx.session, vacancy, application, candidate)
    notifications.notify_new_application(ctx.outbox, vacancy, application, candidate)
    ctx.set_step(Step.idle)
    ctx.reply(
        texts.APPLICATION_SENT.format(position=escape(vacancy.position)),
        [[Button(texts.MY_APPLICATIONS_BUTTON, "cand:my")]],
    )


def _confirm_keyboard() -> Keyboard:
    return [[Button("Отправить", "cand:confirm"), Button("Изменить данные", "cand:edit")]]
