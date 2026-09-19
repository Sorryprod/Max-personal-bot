from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# JSONB в PostgreSQL, обычный JSON в SQLite (для тестов).
JsonType = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


class VacancyStatus(StrEnum):
    active = "active"
    closed = "closed"


class QuestionType(StrEnum):
    yes_no = "yes_no"
    choice = "choice"
    text = "text"


class ApplicationStatus(StrEnum):
    new = "new"
    screened = "screened"
    invited = "invited"
    reserve = "reserve"
    rejected = "rejected"


def _now_column() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


class Employer(Base):
    __tablename__ = "employer"

    id: Mapped[int] = mapped_column(primary_key=True)
    max_user_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    name: Mapped[str] = mapped_column(String(200))
    place_name: Mapped[str] = mapped_column(String(200), default="")
    city: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = _now_column()

    vacancies: Mapped[list["Vacancy"]] = relationship(back_populates="employer")


class Vacancy(Base):
    __tablename__ = "vacancy"

    id: Mapped[int] = mapped_column(primary_key=True)
    employer_id: Mapped[int] = mapped_column(ForeignKey("employer.id", ondelete="CASCADE"), index=True)
    position: Mapped[str] = mapped_column(String(200))
    schedule: Mapped[str] = mapped_column(String(200))
    salary_from: Mapped[int | None] = mapped_column(Integer)
    salary_to: Mapped[int | None] = mapped_column(Integer)
    address: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), default=VacancyStatus.active)
    invite_slug: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = _now_column()

    employer: Mapped[Employer] = relationship(back_populates="vacancies")
    questions: Mapped[list["ScreeningQuestion"]] = relationship(
        back_populates="vacancy", order_by="ScreeningQuestion.position", cascade="all, delete-orphan"
    )
    applications: Mapped[list["Application"]] = relationship(back_populates="vacancy")


class ScreeningQuestion(Base):
    __tablename__ = "screening_question"

    id: Mapped[int] = mapped_column(primary_key=True)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancy.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(String(300))
    qtype: Mapped[str] = mapped_column(String(20))
    options: Mapped[list[str]] = mapped_column(JsonType, default=list)
    is_blocking: Mapped[bool] = mapped_column(Boolean, default=False)
    # Для отсеивающих вопросов — какие ответы считаются подходящими.
    accepted: Mapped[list[str]] = mapped_column(JsonType, default=list)

    vacancy: Mapped[Vacancy] = relationship(back_populates="questions")


class Candidate(Base):
    __tablename__ = "candidate"

    id: Mapped[int] = mapped_column(primary_key=True)
    max_user_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    contact: Mapped[str] = mapped_column(String(100), default="")
    created_at: Mapped[datetime] = _now_column()


class Application(Base):
    __tablename__ = "application"
    __table_args__ = (UniqueConstraint("vacancy_id", "candidate_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancy.id", ondelete="CASCADE"), index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidate.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default=ApplicationStatus.new)
    # Кандидат не прошёл хотя бы один отсеивающий вопрос — только пометка, решает работодатель.
    screening_failed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = _now_column()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    vacancy: Mapped[Vacancy] = relationship(back_populates="applications")
    candidate: Mapped[Candidate] = relationship()
    answers: Mapped[list["Answer"]] = relationship(back_populates="application", cascade="all, delete-orphan")
    slots: Mapped[list["InterviewSlot"]] = relationship(
        back_populates="application", order_by="InterviewSlot.starts_at", cascade="all, delete-orphan"
    )


class Answer(Base):
    __tablename__ = "answer"
    __table_args__ = (UniqueConstraint("application_id", "question_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("application.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("screening_question.id", ondelete="CASCADE"))
    value: Mapped[str] = mapped_column(Text)

    application: Mapped[Application] = relationship(back_populates="answers")
    question: Mapped[ScreeningQuestion] = relationship()


class InterviewSlot(Base):
    __tablename__ = "interview_slot"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("application.id", ondelete="CASCADE"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_chosen: Mapped[bool] = mapped_column(Boolean, default=False)

    application: Mapped[Application] = relationship(back_populates="slots")


class DialogState(Base):
    __tablename__ = "dialog_state"

    max_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    step: Mapped[str] = mapped_column(String(50), default="idle")
    context: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProcessedUpdate(Base):
    __tablename__ = "processed_update"

    # В MAX нет update_id: ключ строится из mid сообщения / callback_id / user+timestamp.
    update_key: Mapped[str] = mapped_column(String(200), primary_key=True)
    processed_at: Mapped[datetime] = _now_column()
