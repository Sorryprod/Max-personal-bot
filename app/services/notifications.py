"""Уведомления сторонам. Сообщения кладутся в Outbox и уходят после коммита."""

from html import escape

from app.db.models import Application, Candidate, Vacancy
from app.messaging import Outbox
from app.services.applinks import AppLinks
from app.services.screening import display_value


def notify_new_application(
    outbox: Outbox, links: AppLinks, vacancy: Vacancy, application: Application, candidate: Candidate
) -> None:
    answers = {a.question_id: a.value for a in application.answers}
    lines = [
        f"🔔 <b>Новый отклик</b> на вакансию «{escape(vacancy.position)}»",
        "",
        f"<b>{escape(candidate.name)}</b>, {escape(candidate.contact)}",
    ]
    for question in vacancy.questions:
        if question.id in answers:
            lines.append(f"• {escape(question.text)} — {escape(display_value(question, answers[question.id]))}")
    if application.screening_failed:
        lines += ["", "⚠️ Не прошёл отсеивающие вопросы"]
    outbox.send(
        vacancy.employer.max_user_id,
        "\n".join(lines),
        [[links.button("Открыть кандидатов", vacancy.employer.max_user_id, vacancy.employer.name,
                       f"vacancy-{vacancy.id}")]],
    )
