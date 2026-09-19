"""Форматирование сообщений бота (HTML, пользовательские данные экранируются)."""

from html import escape

from app.db.models import Vacancy


def salary_text(vacancy: Vacancy) -> str:
    lo, hi = vacancy.salary_from, vacancy.salary_to
    fmt = lambda v: f"{v:,}".replace(",", " ")  # noqa: E731
    if lo and hi:
        return f"{fmt(lo)}–{fmt(hi)} ₽"
    if lo:
        return f"от {fmt(lo)} ₽"
    if hi:
        return f"до {fmt(hi)} ₽"
    return "по договорённости"


def vacancy_card(vacancy: Vacancy) -> str:
    employer = vacancy.employer
    place = ", ".join(p for p in (employer.place_name, employer.city) if p)
    lines = [
        f"<b>{escape(vacancy.position)}</b>",
        escape(place),
        "",
        f"💰 {escape(salary_text(vacancy))}",
        f"🕒 {escape(vacancy.schedule)}",
        f"📍 {escape(vacancy.address)}",
    ]
    return "\n".join(lines)
