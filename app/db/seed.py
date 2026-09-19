"""Синтетические демо-данные. Все люди, точки и вакансии вымышлены.

Запуск:  python -m app.db.seed [--owner MAX_USER_ID]
--owner  — MAX user_id, которому будут приходить уведомления по демо-вакансиям
           (по умолчанию вымышленный работодатель, уведомления никуда не уходят).
Повторный запуск ничего не дублирует.
"""

import argparse
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import (
    Answer,
    Application,
    ApplicationStatus,
    Candidate,
    Employer,
    QuestionType,
    ScreeningQuestion,
    Vacancy,
)
from app.db.session import make_engine, make_session_factory
from app.services.screening import passes

DEMO_EMPLOYER_ID = -1  # отрицательный id заведомо не принадлежит реальному пользователю MAX

DEMO_VACANCIES = [
    {
        "invite_slug": "demo-povar",
        "position": "Повар горячего цеха",
        "schedule": "2/2, с 9:00 до 21:00",
        "salary_from": 55000,
        "salary_to": 70000,
        "address": "Белгород, ул. Примерная, 1",
        "questions": [
            ("Вам есть 18 лет?", QuestionType.yes_no, [], True, ["yes"]),
            ("Есть ли действующая медкнижка?", QuestionType.yes_no, [], True, ["yes"]),
            ("Опыт работы поваром", QuestionType.choice, ["Нет опыта", "До 1 года", "Больше года"], False, []),
        ],
    },
    {
        "invite_slug": "demo-prodavec",
        "position": "Продавец-кассир",
        "schedule": "5/2, с 8:00 до 17:00",
        "salary_from": 45000,
        "salary_to": None,
        "address": "Старый Оскол, мкр. Условный, 5",
        "questions": [
            ("Готовы работать в выходные?", QuestionType.yes_no, [], False, []),
            ("Когда готовы выйти на работу?", QuestionType.choice, ["Сразу", "Через неделю", "Через месяц"],
             False, []),
        ],
    },
]

# Вымышленные кандидаты (id < 0, телефоны из заведомо тестового диапазона +7 900 000-00-xx).
# Ответы — по порядку вопросов вакансии.
DEMO_CANDIDATES = [
    ("demo-povar", -101, "Ирина Соколова", "+79000000001", ["yes", "yes", "Больше года"]),
    ("demo-povar", -102, "Дмитрий Орлов", "+79000000002", ["yes", "no", "До 1 года"]),
    ("demo-povar", -103, "Алина Кузнецова", "+79000000003", ["yes", "yes", "Нет опыта"]),
    ("demo-povar", -104, "Сергей Волков", "+79000000004", ["no", "yes", "Больше года"]),
    ("demo-prodavec", -105, "Ольга Морозова", "+79000000005", ["yes", "Сразу"]),
    ("demo-prodavec", -106, "Павел Лебедев", "+79000000006", ["no", "Через месяц"]),
]


async def seed(session: AsyncSession, owner_max_id: int | None = None, with_candidates: bool = True) -> None:
    max_id = owner_max_id if owner_max_id is not None else DEMO_EMPLOYER_ID
    employer = await session.scalar(select(Employer).where(Employer.max_user_id == max_id))
    if employer is None:
        employer = Employer(max_user_id=max_id, name="Демо-работодатель", place_name="Кафе «Пример»",
                            city="Белгород")
        session.add(employer)
        await session.flush()

    for data in DEMO_VACANCIES:
        if await session.scalar(select(Vacancy.id).where(Vacancy.invite_slug == data["invite_slug"])):
            continue
        vacancy = Vacancy(
            employer_id=employer.id,
            **{k: v for k, v in data.items() if k != "questions"},
        )
        vacancy.questions = [
            ScreeningQuestion(position=i, text=text, qtype=qtype, options=options, is_blocking=blocking,
                              accepted=accepted)
            for i, (text, qtype, options, blocking, accepted) in enumerate(data["questions"])
        ]
        session.add(vacancy)
    await session.flush()
    if with_candidates:
        await _seed_candidates(session)


async def _seed_candidates(session: AsyncSession) -> None:
    for slug, max_id, name, phone, values in DEMO_CANDIDATES:
        if await session.scalar(select(Candidate.id).where(Candidate.max_user_id == max_id)):
            continue
        vacancy = await session.scalar(select(Vacancy).where(Vacancy.invite_slug == slug))
        if vacancy is None:
            continue
        await session.refresh(vacancy, ["questions"])
        candidate = Candidate(max_user_id=max_id, name=name, contact=phone)
        answers = [Answer(question_id=q.id, value=v) for q, v in zip(vacancy.questions, values)]
        failed = any(not passes(q, v) for q, v in zip(vacancy.questions, values))
        session.add(Application(vacancy=vacancy, candidate=candidate, status=ApplicationStatus.screened,
                                screening_failed=failed, answers=answers))
    await session.flush()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Загрузить синтетические демо-данные")
    parser.add_argument("--owner", type=int, default=None, help="MAX user_id владельца демо-вакансий")
    parser.add_argument("--no-candidates", action="store_true", help="не добавлять демо-кандидатов")
    args = parser.parse_args()
    engine = make_engine(get_settings().database_url)
    async with make_session_factory(engine)() as session, session.begin():
        await seed(session, args.owner, with_candidates=not args.no_candidates)
    await engine.dispose()
    print("Демо-данные загружены")


if __name__ == "__main__":
    asyncio.run(main())
