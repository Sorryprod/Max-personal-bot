"""Синтетические демо-данные. Все люди, точки и вакансии вымышлены.

Запуск:
  python -m app.db.seed                    — добавить демо-данные (повторный запуск ничего не дублирует)
  python -m app.db.seed --reset            — вернуть демо-данные в исходное состояние
  python -m app.db.seed --owner MAX_ID     — демо-вакансии принадлежат этому пользователю MAX
                                             (ему будут приходить уведомления по ним)
  python -m app.db.seed --no-candidates    — без демо-кандидатов

Демо-кандидаты имеют отрицательные max_user_id — такие id не бывают у реальных пользователей MAX,
поэтому бот им ничего не отправляет. Телефоны — из заведомо тестового диапазона +7 900 000-00-xx.
"""

import argparse
import asyncio
import secrets

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import (
    Answer,
    Application,
    ApplicationStatus,
    Candidate,
    DialogState,
    Employer,
    InterviewSlot,
    QuestionType,
    ScreeningQuestion,
    Vacancy,
)
from app.db.session import make_engine, make_session_factory
from app.services.screening import passes

DEMO_EMPLOYER_ID = -1
DEMO_SLUG_PREFIX = "demo-"
# Копии-примеры в аккаунтах работодателей. Длина 14 символов — не пересекается
# с обычными ссылками (8 символов), поэтому их можно безопасно удалить при сбросе.
EXAMPLE_SLUG_PREFIX = "example_"
EXAMPLE_SUFFIX = " (пример)"

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

# (слаг вакансии, max_user_id, имя, телефон, ответы по порядку вопросов)
DEMO_CANDIDATES = [
    ("demo-povar", -101, "Ирина Соколова", "+79000000001", ["yes", "yes", "Больше года"]),
    ("demo-povar", -102, "Дмитрий Орлов", "+79000000002", ["yes", "no", "До 1 года"]),
    ("demo-povar", -103, "Алина Кузнецова", "+79000000003", ["yes", "yes", "Нет опыта"]),
    ("demo-povar", -104, "Сергей Волков", "+79000000004", ["no", "yes", "Больше года"]),
    ("demo-prodavec", -105, "Ольга Морозова", "+79000000005", ["yes", "Сразу"]),
    ("demo-prodavec", -106, "Павел Лебедев", "+79000000006", ["no", "Через месяц"]),
]


def _build_vacancy(data: dict, employer: Employer, slug: str, suffix: str = "") -> Vacancy:
    vacancy = Vacancy(
        employer=employer,
        invite_slug=slug,
        position=data["position"] + suffix,
        **{k: v for k, v in data.items() if k not in ("questions", "invite_slug", "position")},
    )
    vacancy.questions = [
        ScreeningQuestion(position=i, text=text, qtype=qtype, options=options, is_blocking=blocking,
                          accepted=accepted)
        for i, (text, qtype, options, blocking, accepted) in enumerate(data["questions"])
    ]
    return vacancy


async def _synthetic_candidate(session: AsyncSession, max_id: int, name: str, phone: str) -> Candidate:
    candidate = await session.scalar(select(Candidate).where(Candidate.max_user_id == max_id))
    if candidate is None:
        candidate = Candidate(max_user_id=max_id, name=name, contact=phone)
        session.add(candidate)
        await session.flush()
    return candidate


async def _add_candidates(session: AsyncSession, vacancy: Vacancy, source_slug: str) -> None:
    await session.flush()
    for slug, max_id, name, phone, values in DEMO_CANDIDATES:
        if slug != source_slug:
            continue
        candidate = await _synthetic_candidate(session, max_id, name, phone)
        exists = await session.scalar(
            select(Application.id).where(Application.vacancy_id == vacancy.id,
                                         Application.candidate_id == candidate.id)
        )
        if exists:
            continue
        pairs = list(zip(vacancy.questions, values))
        session.add(Application(
            vacancy_id=vacancy.id,
            candidate_id=candidate.id,
            status=ApplicationStatus.screened,
            screening_failed=any(not passes(q, v) for q, v in pairs),
            answers=[Answer(question_id=q.id, value=v) for q, v in pairs],
        ))
    await session.flush()


async def seed(session: AsyncSession, owner_max_id: int | None = None, with_candidates: bool = True) -> None:
    max_id = owner_max_id if owner_max_id is not None else DEMO_EMPLOYER_ID
    employer = await session.scalar(select(Employer).where(Employer.max_user_id == max_id))
    if employer is None:
        employer = Employer(max_user_id=max_id, name="Демо-работодатель", place_name="Кафе «Пример»",
                            city="Белгород")
        session.add(employer)
        await session.flush()

    for data in DEMO_VACANCIES:
        vacancy = await session.scalar(select(Vacancy).where(Vacancy.invite_slug == data["invite_slug"]))
        if vacancy is None:
            vacancy = _build_vacancy(data, employer, data["invite_slug"])
            session.add(vacancy)
        if with_candidates:
            await session.flush()
            await session.refresh(vacancy, ["questions"])
            await _add_candidates(session, vacancy, data["invite_slug"])
    await session.flush()


async def reset(session: AsyncSession) -> None:
    """Удаляет демо-вакансии, копии-примеры и синтетических кандидатов со всеми откликами."""
    demo_vacancies = select(Vacancy.id).where(or_(
        Vacancy.invite_slug.startswith(DEMO_SLUG_PREFIX),
        Vacancy.invite_slug.startswith(EXAMPLE_SLUG_PREFIX),
    ))
    synthetic = select(Candidate.id).where(Candidate.max_user_id < 0)
    apps = select(Application.id).where(or_(
        Application.vacancy_id.in_(demo_vacancies), Application.candidate_id.in_(synthetic)
    ))
    await session.execute(delete(Answer).where(Answer.application_id.in_(apps)))
    await session.execute(delete(InterviewSlot).where(InterviewSlot.application_id.in_(apps)))
    await session.execute(delete(Application).where(Application.id.in_(apps)))
    await session.execute(delete(ScreeningQuestion).where(ScreeningQuestion.vacancy_id.in_(demo_vacancies)))
    await session.execute(delete(Vacancy).where(Vacancy.id.in_(demo_vacancies)))
    await session.execute(delete(Candidate).where(Candidate.max_user_id < 0))
    await session.execute(delete(Employer).where(Employer.max_user_id < 0))
    await session.execute(delete(DialogState).where(DialogState.max_user_id < 0))
    await session.flush()
    session.expunge_all()


async def create_example(session: AsyncSession, employer: Employer) -> Vacancy:
    """Копия демо-вакансии с синтетическими кандидатами в аккаунте работодателя —
    чтобы сразу посмотреть сравнение кандидатов и приглашение, не собирая отклики."""
    source = DEMO_VACANCIES[0]
    slug = EXAMPLE_SLUG_PREFIX + secrets.token_urlsafe(4)
    vacancy = _build_vacancy(source, employer, slug, EXAMPLE_SUFFIX)
    session.add(vacancy)
    await session.flush()
    await session.refresh(vacancy, ["questions"])
    await _add_candidates(session, vacancy, source["invite_slug"])
    return vacancy


async def main() -> None:
    parser = argparse.ArgumentParser(description="Синтетические демо-данные")
    parser.add_argument("--owner", type=int, default=None, help="MAX user_id владельца демо-вакансий")
    parser.add_argument("--no-candidates", action="store_true", help="не добавлять демо-кандидатов")
    parser.add_argument("--reset", action="store_true", help="сбросить демо-данные к исходному состоянию")
    args = parser.parse_args()
    engine = make_engine(get_settings().database_url)
    async with make_session_factory(engine)() as session, session.begin():
        if args.reset:
            await reset(session)
        await seed(session, args.owner, with_candidates=not args.no_candidates)
    await engine.dispose()
    print("Демо-данные сброшены и загружены заново" if args.reset else "Демо-данные загружены")


if __name__ == "__main__":
    asyncio.run(main())
