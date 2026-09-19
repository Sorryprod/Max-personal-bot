"""REST для мини-приложения: вакансии работодателя."""

from datetime import datetime
from html import escape
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.api.auth import WebAppUser, current_user
from app.api.deps import api_error, require_employer, unit_of_work
from app.bot import texts
from app.db.models import QuestionType, Vacancy, VacancyStatus
from app.messaging import Button, ButtonKind
from app.services import vacancies
from app.services.screening import NO, YES

router = APIRouter(prefix="/api", tags=["vacancies"])

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]
QuestionText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]
OptionText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
AddressText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=200)]
Salary = Annotated[int | None, Field(default=None, ge=0, le=1_000_000)]


class QuestionIn(BaseModel):
    text: QuestionText
    qtype: QuestionType
    options: list[OptionText] = Field(default_factory=list, max_length=6)
    is_blocking: bool = False
    accepted: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check(self) -> "QuestionIn":
        if self.qtype == QuestionType.choice:
            if len(self.options) < 2 or len(set(self.options)) != len(self.options):
                raise ValueError(f"У вопроса «{self.text}» нужно от 2 до 6 разных вариантов ответа")
            allowed = set(self.options)
        elif self.qtype == QuestionType.yes_no:
            self.options = []
            allowed = {YES, NO}
        else:
            self.options, self.is_blocking = [], False
            allowed = set()
        if not self.is_blocking:
            self.accepted = []
        elif not self.accepted or not set(self.accepted) <= allowed:
            raise ValueError(f"Для отсеивающего вопроса «{self.text}» отметьте подходящие ответы")
        elif set(self.accepted) == allowed:
            raise ValueError(f"В вопросе «{self.text}» подходят все ответы — он никого не отсеивает")
        return self


class VacancyIn(BaseModel):
    position: ShortText
    schedule: ShortText
    salary_from: Salary = None
    salary_to: Salary = None
    address: AddressText
    questions: list[QuestionIn] = Field(default_factory=list, max_length=vacancies.MAX_QUESTIONS)

    @model_validator(mode="after")
    def _check(self) -> "VacancyIn":
        if self.salary_from and self.salary_to and self.salary_from > self.salary_to:
            raise ValueError("Зарплата «от» больше, чем «до»")
        return self


class QuestionOut(BaseModel):
    id: int
    text: str
    qtype: str
    options: list[str]
    is_blocking: bool
    accepted: list[str]


class VacancyOut(BaseModel):
    id: int
    position: str
    schedule: str
    salary_from: int | None
    salary_to: int | None
    address: str
    status: str
    invite_link: str
    created_at: datetime | None
    total: int = 0
    unreviewed: int = 0
    questions: list[QuestionOut] | None = None


class StatusIn(BaseModel):
    status: Literal["active", "closed"]


def vacancy_out(
    request: Request, v: Vacancy, total: int = 0, unreviewed: int = 0, with_questions: bool = False
) -> VacancyOut:
    questions = None
    if with_questions:
        questions = [
            QuestionOut(id=q.id, text=q.text, qtype=q.qtype, options=q.options, is_blocking=q.is_blocking,
                        accepted=q.accepted)
            for q in v.questions
        ]
    return VacancyOut(
        id=v.id,
        position=v.position,
        schedule=v.schedule,
        salary_from=v.salary_from,
        salary_to=v.salary_to,
        address=v.address,
        status=v.status,
        invite_link=request.app.state.messenger.invite_link(v.invite_slug),
        created_at=v.created_at,
        total=total,
        unreviewed=unreviewed,
        questions=questions,
    )


@router.get("/me")
async def me(request: Request, user: WebAppUser = Depends(current_user)) -> dict[str, Any]:
    async with unit_of_work(request) as (session, _):
        employer = await vacancies.get_employer(session, user.id)
    registered = employer is not None and bool(employer.place_name)
    return {
        "user": {"id": user.id, "name": user.full_name},
        "employer": {"place_name": employer.place_name, "city": employer.city} if registered else None,
        "question_templates": vacancies.QUESTION_TEMPLATES,
        "max_questions": vacancies.MAX_QUESTIONS,
    }


@router.get("/vacancies")
async def list_vacancies(request: Request, user: WebAppUser = Depends(current_user)) -> list[VacancyOut]:
    async with unit_of_work(request) as (session, _):
        employer = await require_employer(session, user)
        rows = await vacancies.employer_vacancies(session, employer)
        return [vacancy_out(request, r.vacancy, r.total, r.unreviewed) for r in rows]


@router.post("/vacancies", status_code=201)
async def create_vacancy(request: Request, body: VacancyIn, user: WebAppUser = Depends(current_user)) -> VacancyOut:
    async with unit_of_work(request) as (session, outbox):
        employer = await require_employer(session, user)
        data = vacancies.VacancyInput(
            position=body.position,
            schedule=body.schedule,
            salary_from=body.salary_from,
            salary_to=body.salary_to,
            address=body.address,
            questions=[vacancies.QuestionInput(**q.model_dump()) for q in body.questions],
        )
        vacancy = await vacancies.create_vacancy(session, employer, data)
        link = request.app.state.messenger.invite_link(vacancy.invite_slug)
        outbox.send(
            user.id,
            texts.VACANCY_PUBLISHED.format(position=escape(vacancy.position), link=escape(link)),
            [
                [Button(texts.COPY_LINK_BUTTON, link, ButtonKind.clipboard)],
                [Button(texts.EMP_CABINET_BUTTON, kind=ButtonKind.app)],
            ],
        )
        return vacancy_out(request, vacancy, with_questions=True)


async def _own_vacancy(session, user: WebAppUser, vacancy_id: int) -> Vacancy:
    employer = await require_employer(session, user)
    vacancy = await vacancies.employer_vacancy(session, employer, vacancy_id)
    if vacancy is None:
        raise api_error(404, "not_found", "Вакансия не найдена")
    return vacancy


@router.get("/vacancies/{vacancy_id}")
async def get_vacancy(request: Request, vacancy_id: int, user: WebAppUser = Depends(current_user)) -> VacancyOut:
    async with unit_of_work(request) as (session, _):
        vacancy = await _own_vacancy(session, user, vacancy_id)
        return vacancy_out(request, vacancy, with_questions=True)


@router.patch("/vacancies/{vacancy_id}")
async def set_vacancy_status(
    request: Request, vacancy_id: int, body: StatusIn, user: WebAppUser = Depends(current_user)
) -> VacancyOut:
    async with unit_of_work(request) as (session, _):
        vacancy = await _own_vacancy(session, user, vacancy_id)
        vacancy.status = VacancyStatus(body.status)
        await session.flush()
        return vacancy_out(request, vacancy, with_questions=True)
