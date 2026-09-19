"""Отклики глазами работодателя: список, сравнение, смена статуса."""

from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Application, ApplicationStatus, Employer, Vacancy
from app.messaging import Outbox
from app.services import notifications

# Статусы, которые работодатель ставит напрямую; приглашение идёт через выбор слотов.
MANUAL_STATUSES = {ApplicationStatus.screened, ApplicationStatus.reserve, ApplicationStatus.rejected}

_STATUS_ORDER = case(
    (Application.status == ApplicationStatus.screened, 0),
    (Application.status == ApplicationStatus.invited, 1),
    (Application.status == ApplicationStatus.reserve, 2),
    else_=3,
)


async def vacancy_applications(session: AsyncSession, vacancy: Vacancy) -> list[Application]:
    """Заполненные отклики: сначала ждущие решения, прошедшие отсев — выше."""
    result = await session.scalars(
        select(Application)
        .where(Application.vacancy_id == vacancy.id, Application.status != ApplicationStatus.new)
        .options(
            selectinload(Application.candidate),
            selectinload(Application.answers),
            selectinload(Application.slots),
        )
        .order_by(_STATUS_ORDER, Application.screening_failed, Application.created_at.desc())
    )
    return list(result)


async def employer_application(session: AsyncSession, employer: Employer, application_id: int) -> Application | None:
    return await session.scalar(
        select(Application)
        .join(Vacancy)
        .where(
            Application.id == application_id,
            Vacancy.employer_id == employer.id,
            Application.status != ApplicationStatus.new,
        )
        .options(
            selectinload(Application.candidate),
            selectinload(Application.answers),
            selectinload(Application.slots),
            selectinload(Application.vacancy).selectinload(Vacancy.employer),
            selectinload(Application.vacancy).selectinload(Vacancy.questions),
        )
    )


def set_status(outbox: Outbox, application: Application, status: ApplicationStatus) -> bool:
    """Меняет статус и уведомляет кандидата. False — статус и так такой."""
    if application.status == status:
        return False
    application.status = status
    if status != ApplicationStatus.invited:
        # Слоты прошлого приглашения больше не действуют.
        application.slots.clear()
    notifications.notify_status_changed(outbox, application)
    return True
