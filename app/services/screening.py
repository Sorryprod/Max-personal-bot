"""Логика отклика: отсеивающие вопросы, ответы, статусы. Не зависит от мессенджера."""

import re
import secrets
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    Answer,
    Application,
    ApplicationStatus,
    Candidate,
    QuestionType,
    ScreeningQuestion,
    Vacancy,
    VacancyStatus,
)

YES, NO = "yes", "no"
YES_NO_LABELS = {YES: "Да", NO: "Нет"}

STATUS_LABELS = {
    ApplicationStatus.new: "анкета не заполнена",
    ApplicationStatus.screened: "на рассмотрении",
    ApplicationStatus.invited: "приглашение на собеседование",
    ApplicationStatus.reserve: "в резерве",
    ApplicationStatus.rejected: "отказ",
}

NAME_MIN, NAME_MAX = 2, 100
_NAME_RE = re.compile(r"^[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё .'-]*$")
_PHONE_CLEAN_RE = re.compile(r"[\s()\-.]")


def new_invite_slug() -> str:
    # token_urlsafe даёт [A-Za-z0-9_-] — ровно то, что MAX допускает в payload ссылки.
    return secrets.token_urlsafe(6)


async def get_vacancy_by_slug(session: AsyncSession, slug: str) -> Vacancy | None:
    return await session.scalar(
        select(Vacancy)
        .where(Vacancy.invite_slug == slug)
        .options(selectinload(Vacancy.questions), selectinload(Vacancy.employer))
    )


async def get_vacancy(session: AsyncSession, vacancy_id: int) -> Vacancy | None:
    return await session.scalar(
        select(Vacancy)
        .where(Vacancy.id == vacancy_id)
        .options(selectinload(Vacancy.questions), selectinload(Vacancy.employer))
    )


def is_open(vacancy: Vacancy | None) -> bool:
    return vacancy is not None and vacancy.status == VacancyStatus.active


async def get_or_create_candidate(session: AsyncSession, max_user_id: int, name: str) -> Candidate:
    candidate = await session.scalar(select(Candidate).where(Candidate.max_user_id == max_user_id))
    if candidate is None:
        candidate = Candidate(max_user_id=max_user_id, name=name[:NAME_MAX], contact="")
        session.add(candidate)
        await session.flush()
    return candidate


async def find_application(session: AsyncSession, vacancy_id: int, candidate_id: int) -> Application | None:
    return await session.scalar(
        select(Application)
        .where(Application.vacancy_id == vacancy_id, Application.candidate_id == candidate_id)
        .options(selectinload(Application.answers))
    )


async def start_application(
    session: AsyncSession, vacancy: Vacancy, candidate: Candidate
) -> tuple[Application, bool]:
    """Создаёт черновик отклика (status=new). Возвращает (отклик, создан_ли_сейчас)."""
    application = await find_application(session, vacancy.id, candidate.id)
    if application is not None:
        return application, False
    # answers=[] — коллекция сразу загружена, без ленивой подгрузки в async.
    application = Application(
        vacancy_id=vacancy.id, candidate_id=candidate.id, status=ApplicationStatus.new, answers=[]
    )
    session.add(application)
    await session.flush()
    return application, True


def next_question(vacancy: Vacancy, application: Application) -> ScreeningQuestion | None:
    answered = {a.question_id for a in application.answers}
    for question in vacancy.questions:
        if question.id not in answered:
            return question
    return None


def normalize_answer(question: ScreeningQuestion, raw: str) -> str | None:
    """Приводит ответ к хранимому виду; None — ответ некорректен для этого вопроса."""
    raw = raw.strip()
    if question.qtype == QuestionType.yes_no:
        lowered = raw.lower()
        if lowered in (YES, "да"):
            return YES
        if lowered in (NO, "нет"):
            return NO
        return None
    if question.qtype == QuestionType.choice:
        if raw.isdigit() and int(raw) < len(question.options):
            return question.options[int(raw)]
        for option in question.options:
            if option.lower() == raw.lower():
                return option
        return None
    return raw[:1000] or None


def passes(question: ScreeningQuestion, value: str) -> bool:
    if not question.is_blocking or question.qtype == QuestionType.text or not question.accepted:
        return True
    return value in question.accepted


def display_value(question: ScreeningQuestion, value: str) -> str:
    if question.qtype == QuestionType.yes_no:
        return YES_NO_LABELS.get(value, value)
    return value


async def record_answer(
    session: AsyncSession, application: Application, question: ScreeningQuestion, value: str
) -> None:
    if any(a.question_id == question.id for a in application.answers):
        return
    answer = Answer(application_id=application.id, question_id=question.id, value=value)
    session.add(answer)
    application.answers.append(answer)
    await session.flush()


def validate_name(raw: str) -> str | None:
    name = " ".join(raw.split())
    if NAME_MIN <= len(name) <= NAME_MAX and _NAME_RE.match(name):
        return name
    return None


def normalize_phone(raw: str) -> str | None:
    phone = _PHONE_CLEAN_RE.sub("", raw.strip())
    digits = phone[1:] if phone.startswith("+") else phone
    if not digits.isdigit():
        return None
    if len(digits) == 11 and digits[0] in "78":
        return "+7" + digits[1:]
    if len(digits) == 10 and digits[0] == "9":
        return "+7" + digits
    if 10 <= len(digits) <= 15 and phone.startswith("+"):
        return "+" + digits
    return None


@dataclass
class SubmitResult:
    application: Application
    failed_questions: list[ScreeningQuestion]


async def submit_application(
    session: AsyncSession, vacancy: Vacancy, application: Application, candidate: Candidate
) -> SubmitResult:
    """Анкета заполнена: считаем отсев (только пометка) и переводим в screened."""
    answers = {a.question_id: a.value for a in application.answers}
    failed = [q for q in vacancy.questions if q.id in answers and not passes(q, answers[q.id])]
    application.screening_failed = bool(failed)
    if application.status == ApplicationStatus.new:
        application.status = ApplicationStatus.screened
    await session.flush()
    return SubmitResult(application, failed)


async def candidate_applications(session: AsyncSession, max_user_id: int) -> list[Application]:
    result = await session.scalars(
        select(Application)
        .join(Candidate)
        .where(Candidate.max_user_id == max_user_id)
        .options(selectinload(Application.vacancy).selectinload(Vacancy.employer))
        .order_by(Application.created_at.desc())
    )
    return list(result)
