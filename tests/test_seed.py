from sqlalchemy import func, select

from app.db.models import Application, Candidate, Vacancy
from app.db.seed import DEMO_CANDIDATES, DEMO_VACANCIES, seed


async def test_seed_is_idempotent_and_synthetic(session_factory):
    for _ in range(2):
        async with session_factory() as session, session.begin():
            await seed(session)
    async with session_factory() as session:
        assert await session.scalar(select(func.count(Vacancy.id))) == len(DEMO_VACANCIES)
        assert await session.scalar(select(func.count(Application.id))) == len(DEMO_CANDIDATES)
        # все демо-кандидаты — с отрицательными id, т. е. заведомо не реальные пользователи MAX
        assert await session.scalar(select(func.max(Candidate.max_user_id))) < 0
        failed = await session.scalar(select(func.count()).where(Application.screening_failed.is_(True)))
    assert failed == 2  # Дмитрий без медкнижки, Сергей младше 18
