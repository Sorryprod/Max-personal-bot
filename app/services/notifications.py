"""Уведомления сторонам. Сообщения кладутся в Outbox и уходят после коммита."""

from html import escape

from app.db.models import Application, ApplicationStatus, Candidate, InterviewSlot, Vacancy
from app.messaging import Button, Outbox
from app.services.applinks import AppLinks
from app.services.interviews import format_slot
from app.services.screening import display_value


def notify_new_application(
    outbox: Outbox, links: AppLinks, vacancy: Vacancy, application: Application, candidate: Candidate
) -> None:
    answers = {a.question_id: a.value for a in application.answers}
    lines = [
        f"<b>Новый отклик</b> на вакансию «{escape(vacancy.position)}»",
        "",
        f"<b>{escape(candidate.name)}</b>, {escape(candidate.contact)}",
    ]
    for question in vacancy.questions:
        if question.id in answers:
            lines.append(f"{escape(question.text)} — <b>{escape(display_value(question, answers[question.id]))}</b>")
    if application.screening_failed:
        lines += ["", "<b>Внимание:</b> не прошёл отсеивающие вопросы"]
    outbox.send(
        vacancy.employer.max_user_id,
        "\n".join(lines),
        [[_open_vacancy(links, vacancy)]],
    )


def notify_status_changed(outbox: Outbox, application: Application) -> None:
    """Кандидат узнаёт о решении работодателя, а не пропадает в тишине."""
    vacancy = application.vacancy
    position = escape(vacancy.position)
    place = escape(vacancy.employer.place_name)
    match application.status:
        case ApplicationStatus.reserve:
            text = (
                f"По вакансии «{position}» ({place}) вас добавили в резерв.\n\n"
                "Если место освободится, работодатель напишет вам здесь."
            )
        case ApplicationStatus.rejected:
            text = (
                f"По вакансии «{position}» ({place}) работодатель выбрал другого кандидата.\n\n"
                "Спасибо за отклик и удачи в поиске работы!"
            )
        case _:
            return  # «на рассмотрении» — внутренний статус, кандидата не тревожим
    outbox.send(application.candidate.max_user_id, text)


def notify_invitation(outbox: Outbox, application: Application) -> None:
    vacancy = application.vacancy
    employer = vacancy.employer
    place = ", ".join(p for p in (employer.place_name, employer.city) if p)
    text = (
        "<b>Приглашение на собеседование</b>\n\n"
        f"Вакансия «{escape(vacancy.position)}» — {escape(place)}\n"
        f"<b>Адрес:</b> {escape(vacancy.address)}\n\n"
        "Выберите удобное время:"
    )
    keyboard = [[Button(format_slot(slot.starts_at), f"cand:slot:{slot.id}")] for slot in application.slots]
    keyboard.append([Button("Ни одно время не подходит", f"cand:noslot:{application.id}")])
    outbox.send(application.candidate.max_user_id, text, keyboard)


def notify_slot_chosen(outbox: Outbox, links: AppLinks, application: Application, slot: InterviewSlot) -> None:
    vacancy = application.vacancy
    candidate = application.candidate
    outbox.send(
        vacancy.employer.max_user_id,
        "<b>Собеседование назначено</b>\n\n"
        f"{escape(candidate.name)}, {escape(candidate.contact)} — «{escape(vacancy.position)}»\n"
        f"<b>Время:</b> {format_slot(slot.starts_at)}",
        [[_open_vacancy(links, vacancy)]],
    )


def notify_slots_declined(outbox: Outbox, links: AppLinks, application: Application) -> None:
    vacancy = application.vacancy
    candidate = application.candidate
    outbox.send(
        vacancy.employer.max_user_id,
        "<b>Кандидату не подошло время</b>\n\n"
        f"{escape(candidate.name)}, {escape(candidate.contact)} — «{escape(vacancy.position)}».\n"
        "Предложите другие варианты в карточке кандидата или позвоните ему.",
        [[_open_vacancy(links, vacancy)]],
    )


def _open_vacancy(links: AppLinks, vacancy: Vacancy):
    return links.button("Открыть кандидатов", vacancy.employer.max_user_id, vacancy.employer.name,
                        f"vacancy-{vacancy.id}")
