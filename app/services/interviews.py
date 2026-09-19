"""Приглашение на собеседование: слоты от работодателя, выбор времени кандидатом."""

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from functools import lru_cache
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.db.models import Application, ApplicationStatus, InterviewSlot, Vacancy

MIN_SLOTS, MAX_SLOTS = 2, 3
MIN_LEAD = timedelta(minutes=30)  # слот не раньше чем через полчаса
MAX_AHEAD = timedelta(days=60)

_WEEKDAYS = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
_MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября",
           "октября", "ноября", "декабря"]


@lru_cache
def local_tz() -> ZoneInfo:
    return ZoneInfo(get_settings().app_timezone)


def as_utc(dt: datetime) -> datetime:
    """Время без пояса считаем местным (так его вводит работодатель); SQLite отдаёт naive UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=local_tz()).astimezone(UTC)
    return dt.astimezone(UTC)


def _stored_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def format_slot(dt: datetime) -> str:
    local = _stored_utc(dt).astimezone(local_tz())
    return f"{_WEEKDAYS[local.weekday()]}, {local.day} {_MONTHS[local.month - 1]}, {local:%H:%M}"


class SlotError(ValueError):
    pass


def validate_slots(slots: list[datetime], now: datetime | None = None) -> list[datetime]:
    now = now or datetime.now(UTC)
    normalized = sorted({as_utc(s) for s in slots})
    if len(normalized) != len(slots):
        raise SlotError("Время собеседования не должно повторяться")
    if not MIN_SLOTS <= len(normalized) <= MAX_SLOTS:
        raise SlotError(f"Предложите от {MIN_SLOTS} до {MAX_SLOTS} вариантов времени")
    for slot in normalized:
        if slot < now + MIN_LEAD:
            raise SlotError(f"Время {format_slot(slot)} уже прошло или слишком близко")
        if slot > now + MAX_AHEAD:
            raise SlotError("Собеседование можно назначить не дальше чем на 60 дней вперёд")
    return normalized


async def invite(session: AsyncSession, application: Application, slots: list[datetime]) -> None:
    """Переводит отклик в «приглашён» с новым набором слотов (старые, если были, заменяются)."""
    validated = validate_slots(slots)
    application.status = ApplicationStatus.invited
    application.slots.clear()
    await session.flush()
    for starts_at in validated:
        application.slots.append(InterviewSlot(starts_at=starts_at, is_chosen=False))
    await session.flush()


def chosen_slot(application: Application) -> InterviewSlot | None:
    return next((s for s in application.slots if s.is_chosen), None)


class ChooseResult(StrEnum):
    ok = "ok"
    not_found = "not_found"  # чужой или удалённый слот
    inactive = "inactive"  # приглашение отменено или заменено
    already = "already"  # время уже выбрано


async def _application_for(session: AsyncSession, application_id: int) -> Application | None:
    return await session.scalar(
        select(Application)
        .where(Application.id == application_id)
        .options(
            selectinload(Application.slots),
            selectinload(Application.candidate),
            selectinload(Application.vacancy).selectinload(Vacancy.employer),
        )
    )


async def choose_slot(
    session: AsyncSession, max_user_id: int, slot_id: int
) -> tuple[ChooseResult, Application | None, InterviewSlot | None]:
    slot = await session.get(InterviewSlot, slot_id)
    application = await _application_for(session, slot.application_id) if slot else None
    if slot is None or application is None or application.candidate.max_user_id != max_user_id:
        return ChooseResult.not_found, None, None
    if application.status != ApplicationStatus.invited:
        return ChooseResult.inactive, application, None
    current = chosen_slot(application)
    if current is not None:
        return ChooseResult.already, application, current
    slot.is_chosen = True
    await session.flush()
    return ChooseResult.ok, application, slot


async def decline_slots(
    session: AsyncSession, max_user_id: int, application_id: int
) -> tuple[ChooseResult, Application | None]:
    application = await _application_for(session, application_id)
    if application is None or application.candidate.max_user_id != max_user_id:
        return ChooseResult.not_found, None
    if application.status != ApplicationStatus.invited:
        return ChooseResult.inactive, application
    if chosen_slot(application) is not None:
        return ChooseResult.already, application
    return ChooseResult.ok, application
