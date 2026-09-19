"""REST для мини-приложения: кандидаты по вакансии, сравнение, смена статуса."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.api.auth import WebAppUser, current_user
from app.api.deps import api_error, require_employer, unit_of_work
from app.api.vacancies import VacancyOut, vacancy_out
from app.db.models import Application, ApplicationStatus, Vacancy
from app.services import applications, vacancies
from app.services.screening import display_value, passes

router = APIRouter(prefix="/api", tags=["applications"])


class AnswerOut(BaseModel):
    question_id: int
    value: str
    display: str
    passed: bool


class SlotOut(BaseModel):
    id: int
    starts_at: datetime
    is_chosen: bool


class ApplicationOut(BaseModel):
    id: int
    status: str
    screening_failed: bool
    created_at: datetime | None
    name: str
    contact: str
    answers: list[AnswerOut]
    slots: list[SlotOut]


class VacancyApplicationsOut(BaseModel):
    vacancy: VacancyOut
    applications: list[ApplicationOut]


class StatusIn(BaseModel):
    status: Literal["screened", "reserve", "rejected"]


def application_out(application: Application, vacancy: Vacancy) -> ApplicationOut:
    questions = {q.id: q for q in vacancy.questions}
    answers = []
    for answer in application.answers:
        question = questions.get(answer.question_id)
        if question is None:
            continue
        answers.append(AnswerOut(
            question_id=question.id,
            value=answer.value,
            display=display_value(question, answer.value),
            passed=passes(question, answer.value),
        ))
    return ApplicationOut(
        id=application.id,
        status=application.status,
        screening_failed=application.screening_failed,
        created_at=application.created_at,
        name=application.candidate.name,
        contact=application.candidate.contact,
        answers=answers,
        slots=[SlotOut(id=s.id, starts_at=s.starts_at, is_chosen=s.is_chosen) for s in application.slots],
    )


@router.get("/vacancies/{vacancy_id}/applications")
async def list_applications(
    request: Request, vacancy_id: int, user: WebAppUser = Depends(current_user)
) -> VacancyApplicationsOut:
    async with unit_of_work(request) as (session, _):
        employer = await require_employer(session, user)
        vacancy = await vacancies.employer_vacancy(session, employer, vacancy_id)
        if vacancy is None:
            raise api_error(404, "not_found", "Вакансия не найдена")
        items = await applications.vacancy_applications(session, vacancy)
        return VacancyApplicationsOut(
            vacancy=vacancy_out(request, vacancy, with_questions=True),
            applications=[application_out(a, vacancy) for a in items],
        )


@router.patch("/applications/{application_id}")
async def set_application_status(
    request: Request, application_id: int, body: StatusIn, user: WebAppUser = Depends(current_user)
) -> ApplicationOut:
    async with unit_of_work(request) as (session, outbox):
        employer = await require_employer(session, user)
        application = await applications.employer_application(session, employer, application_id)
        if application is None:
            raise api_error(404, "not_found", "Отклик не найден")
        applications.set_status(outbox, application, ApplicationStatus(body.status))
        await session.flush()
        return application_out(application, application.vacancy)
