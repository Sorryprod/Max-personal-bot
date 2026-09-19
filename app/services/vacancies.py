"""Работодатель и вакансии: регистрация точки, создание вакансии, списки. Не зависит от мессенджера."""

from dataclasses import dataclass

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    Application,
    ApplicationStatus,
    Employer,
    QuestionType,
    ScreeningQuestion,
    Vacancy,
    VacancyStatus,
)
from app.services.screening import YES, new_invite_slug

MAX_QUESTIONS = 3

# Города и районы Белгородской области — кнопками в чате, чтобы не печатать.
BELGOROD_CITIES = ["Белгород", "Старый Оскол", "Губкин", "Шебекино", "Алексеевка", "Валуйки"]

QUESTION_TEMPLATES: list[dict] = [
    {"text": "Вам есть 18 лет?", "qtype": QuestionType.yes_no, "options": [], "is_blocking": True,
     "accepted": [YES]},
    {"text": "Есть ли действующая медкнижка?", "qtype": QuestionType.yes_no, "options": [],
     "is_blocking": True, "accepted": [YES]},
    {"text": "Вам подходит указанный график работы?", "qtype": QuestionType.yes_no, "options": [],
     "is_blocking": True, "accepted": [YES]},
    {"text": "Есть ли гражданство РФ или разрешение на работу?", "qtype": QuestionType.yes_no, "options": [],
     "is_blocking": True, "accepted": [YES]},
    {"text": "Есть ли опыт работы на похожей должности?", "qtype": QuestionType.choice,
     "options": ["Нет опыта", "До 1 года", "Больше года"], "is_blocking": False, "accepted": []},
    {"text": "Когда готовы выйти на работу?", "qtype": QuestionType.choice,
     "options": ["Сразу", "Через неделю", "Через месяц"], "is_blocking": False, "accepted": []},
]


async def get_employer(session: AsyncSession, max_user_id: int) -> Employer | None:
    return await session.scalar(select(Employer).where(Employer.max_user_id == max_user_id))


async def upsert_employer(
    session: AsyncSession, max_user_id: int, name: str, place_name: str, city: str
) -> Employer:
    employer = await get_employer(session, max_user_id)
    if employer is None:
        employer = Employer(max_user_id=max_user_id, name=name[:200])
        session.add(employer)
    employer.place_name = place_name
    employer.city = city
    await session.flush()
    return employer


@dataclass
class QuestionInput:
    text: str
    qtype: QuestionType
    options: list[str]
    is_blocking: bool
    accepted: list[str]


@dataclass
class VacancyInput:
    position: str
    schedule: str
    salary_from: int | None
    salary_to: int | None
    address: str
    questions: list[QuestionInput]


async def create_vacancy(session: AsyncSession, employer: Employer, data: VacancyInput) -> Vacancy:
    vacancy = Vacancy(
        employer_id=employer.id,
        position=data.position,
        schedule=data.schedule,
        salary_from=data.salary_from,
        salary_to=data.salary_to,
        address=data.address,
        status=VacancyStatus.active,
        invite_slug=await _unique_slug(session),
    )
    vacancy.questions = [
        ScreeningQuestion(
            position=i,
            text=q.text,
            qtype=q.qtype,
            options=q.options if q.qtype == QuestionType.choice else [],
            is_blocking=q.is_blocking and q.qtype != QuestionType.text,
            accepted=q.accepted if q.is_blocking else [],
        )
        for i, q in enumerate(data.questions[:MAX_QUESTIONS])
    ]
    vacancy.employer = employer
    session.add(vacancy)
    await session.flush()
    return vacancy


async def _unique_slug(session: AsyncSession) -> str:
    while True:
        slug = new_invite_slug()
        if not await session.scalar(select(Vacancy.id).where(Vacancy.invite_slug == slug)):
            return slug


@dataclass
class VacancySummary:
    vacancy: Vacancy
    total: int  # заполненные отклики
    unreviewed: int  # ждут решения работодателя


async def employer_vacancies(session: AsyncSession, employer: Employer) -> list[VacancySummary]:
    completed = Application.status != ApplicationStatus.new
    stmt = (
        select(
            Vacancy,
            func.count(case((completed, Application.id))),
            func.count(case((Application.status == ApplicationStatus.screened, Application.id))),
        )
        .outerjoin(Application, Application.vacancy_id == Vacancy.id)
        .where(Vacancy.employer_id == employer.id)
        .group_by(Vacancy.id)
        .order_by(Vacancy.created_at.desc(), Vacancy.id.desc())
    )
    rows = await session.execute(stmt)
    return [VacancySummary(v, total, unreviewed) for v, total, unreviewed in rows]


async def employer_vacancy(session: AsyncSession, employer: Employer, vacancy_id: int) -> Vacancy | None:
    return await session.scalar(
        select(Vacancy)
        .where(Vacancy.id == vacancy_id, Vacancy.employer_id == employer.id)
        .options(selectinload(Vacancy.questions), selectinload(Vacancy.employer))
    )
