"""Данные пользователя: что хранится и полное удаление по запросу (152-ФЗ)."""

from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Answer,
    Application,
    Candidate,
    DialogState,
    Employer,
    InterviewSlot,
    ScreeningQuestion,
    Vacancy,
)


@dataclass
class UserData:
    applications: int = 0
    vacancies: int = 0
    is_candidate: bool = False
    is_employer: bool = False

    @property
    def empty(self) -> bool:
        return not (self.is_candidate or self.is_employer)


async def user_data(session: AsyncSession, max_user_id: int) -> UserData:
    data = UserData()
    candidate_id = await session.scalar(select(Candidate.id).where(Candidate.max_user_id == max_user_id))
    if candidate_id:
        data.is_candidate = True
        data.applications = await session.scalar(
            select(func.count(Application.id)).where(Application.candidate_id == candidate_id)
        ) or 0
    employer_id = await session.scalar(select(Employer.id).where(Employer.max_user_id == max_user_id))
    if employer_id:
        data.is_employer = True
        data.vacancies = await session.scalar(
            select(func.count(Vacancy.id)).where(Vacancy.employer_id == employer_id)
        ) or 0
    return data


async def _delete_applications(session: AsyncSession, where) -> None:
    app_ids = select(Application.id).where(where)
    await session.execute(delete(Answer).where(Answer.application_id.in_(app_ids)))
    await session.execute(delete(InterviewSlot).where(InterviewSlot.application_id.in_(app_ids)))
    await session.execute(delete(Application).where(where))


async def delete_user_data(session: AsyncSession, max_user_id: int) -> UserData:
    """Удаляет всё, что связано с пользователем: отклики, вакансии с откликами на них, состояние диалога.

    Удаление явное, по таблицам: не зависит от того, включены ли каскады FK в конкретной СУБД.
    """
    data = await user_data(session, max_user_id)

    candidate_id = await session.scalar(select(Candidate.id).where(Candidate.max_user_id == max_user_id))
    if candidate_id:
        await _delete_applications(session, Application.candidate_id == candidate_id)
        await session.execute(delete(Candidate).where(Candidate.id == candidate_id))

    employer_id = await session.scalar(select(Employer.id).where(Employer.max_user_id == max_user_id))
    if employer_id:
        vacancy_ids = select(Vacancy.id).where(Vacancy.employer_id == employer_id)
        await _delete_applications(session, Application.vacancy_id.in_(vacancy_ids))
        await session.execute(delete(ScreeningQuestion).where(ScreeningQuestion.vacancy_id.in_(vacancy_ids)))
        await session.execute(delete(Vacancy).where(Vacancy.employer_id == employer_id))
        await session.execute(delete(Employer).where(Employer.id == employer_id))

    await session.execute(delete(DialogState).where(DialogState.max_user_id == max_user_id))
    session.expunge_all()  # объекты в сессии больше не соответствуют БД
    return data
