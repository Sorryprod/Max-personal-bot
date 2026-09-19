import pytest
from sqlalchemy import select

from app.db.models import Application, ApplicationStatus, Candidate
from app.db.seed import DEMO_EMPLOYER_ID, seed
from tests.helpers import buttons, contact, press, start, text

CANDIDATE = 1001
OWNER = 2002


@pytest.fixture
async def demo(session_factory):
    async with session_factory() as session, session.begin():
        await seed(session, owner_max_id=OWNER, with_candidates=False)


async def _payload(messenger, label: str) -> str:
    for button in buttons(messenger.sent[-1]):
        if button.text == label:
            return button.payload
    raise AssertionError(f"нет кнопки {label!r} в {messenger.sent[-1]}")


async def test_full_candidate_path(demo, dispatcher, messenger, session_factory):
    await dispatcher.handle(start(CANDIDATE, "demo-povar"))
    assert "Повар горячего цеха" in messenger.sent[-1].text
    await dispatcher.handle(press(CANDIDATE, await _payload(messenger, "Откликнуться")))

    assert "Вопрос 1 из 3" in messenger.sent[-1].text
    await dispatcher.handle(press(CANDIDATE, await _payload(messenger, "Да")))
    assert "Вопрос 2 из 3" in messenger.sent[-1].text
    await dispatcher.handle(press(CANDIDATE, await _payload(messenger, "Нет")))  # отсеивающий — не прошёл
    await dispatcher.handle(press(CANDIDATE, await _payload(messenger, "Больше года")))

    assert "Как к вам обращаться" in messenger.sent[-1].text
    await dispatcher.handle(text(CANDIDATE, "А1"))  # некорректное имя
    assert "от 2 до 100 букв" in messenger.sent[-1].text
    await dispatcher.handle(press(CANDIDATE, await _payload(messenger, "Да, Анна Петрова")))

    await dispatcher.handle(text(CANDIDATE, "позвоните мне"))  # некорректный телефон
    assert "распознать номер" in messenger.sent[-1].text
    await dispatcher.handle(contact(CANDIDATE, "79991234567"))

    to_owner = [m for m in messenger.sent if m.user_id == OWNER]
    assert len(to_owner) == 1 and "Новый отклик" in to_owner[0].text
    assert "Не прошёл отсеивающие" in to_owner[0].text
    assert "отправлен" in messenger.sent[-1].text

    async with session_factory() as session:
        application = await session.scalar(select(Application))
        candidate = await session.scalar(select(Candidate))
    assert application.status == ApplicationStatus.screened
    assert application.screening_failed is True
    assert candidate.contact == "+79991234567" and candidate.name == "Анна Петрова"

    # повторный переход по ссылке показывает статус, а не новую анкету
    await dispatcher.handle(start(CANDIDATE, "demo-povar"))
    assert "уже откликались" in messenger.sent[-1].text


async def test_text_instead_of_button_reasks(demo, dispatcher, messenger):
    await dispatcher.handle(start(CANDIDATE, "demo-povar"))
    await dispatcher.handle(press(CANDIDATE, await _payload(messenger, "Откликнуться")))
    await dispatcher.handle(text(CANDIDATE, "может быть"))
    assert "выберите вариант кнопкой" in messenger.sent[-1].text
    assert "Вопрос 1 из 3" in messenger.sent[-1].text
    await dispatcher.handle(text(CANDIDATE, "да"))  # «да» текстом тоже принимается
    assert "Вопрос 2 из 3" in messenger.sent[-1].text


async def test_resume_after_interruption(demo, dispatcher, messenger):
    await dispatcher.handle(start(CANDIDATE, "demo-povar"))
    await dispatcher.handle(press(CANDIDATE, await _payload(messenger, "Откликнуться")))
    await dispatcher.handle(press(CANDIDATE, await _payload(messenger, "Да")))
    await dispatcher.handle(start(CANDIDATE))  # ушёл в главное меню
    await dispatcher.handle(start(CANDIDATE, "demo-povar"))  # вернулся по ссылке
    assert "Вопрос 2 из 3" in messenger.sent[-1].text


async def test_stale_button_is_ignored(demo, dispatcher, messenger):
    await dispatcher.handle(start(CANDIDATE, "demo-povar"))
    await dispatcher.handle(press(CANDIDATE, await _payload(messenger, "Откликнуться")))
    yes = await _payload(messenger, "Да")
    await dispatcher.handle(press(CANDIDATE, yes))
    sent_before = len(messenger.sent)
    await dispatcher.handle(press(CANDIDATE, yes))  # старая кнопка первого вопроса
    assert len(messenger.sent) == sent_before
    assert messenger.answers[-1].notification == "Этот вопрос уже пройден"


async def test_second_application_reuses_contact(demo, dispatcher, messenger):
    await dispatcher.handle(start(CANDIDATE, "demo-prodavec"))
    await dispatcher.handle(press(CANDIDATE, await _payload(messenger, "Откликнуться")))
    await dispatcher.handle(press(CANDIDATE, await _payload(messenger, "Да")))
    await dispatcher.handle(press(CANDIDATE, await _payload(messenger, "Сразу")))
    await dispatcher.handle(text(CANDIDATE, "Анна"))
    await dispatcher.handle(text(CANDIDATE, "8 (999) 123-45-67"))

    await dispatcher.handle(start(CANDIDATE, "demo-povar"))
    await dispatcher.handle(press(CANDIDATE, await _payload(messenger, "Откликнуться")))
    for label in ("Да", "Да", "Нет опыта"):
        await dispatcher.handle(press(CANDIDATE, await _payload(messenger, label)))
    assert "+79991234567" in messenger.sent[-1].text
    await dispatcher.handle(press(CANDIDATE, await _payload(messenger, "Отправить")))
    assert "отправлен" in messenger.sent[-1].text


async def test_unknown_or_closed_vacancy(demo, dispatcher, messenger):
    await dispatcher.handle(start(CANDIDATE, "no-such-slug"))
    assert "не найдена" in messenger.sent[-1].text


async def test_notification_to_fake_demo_employer_does_not_break(session_factory, dispatcher, messenger):
    async with session_factory() as session, session.begin():
        await seed(session, with_candidates=False)  # владелец — вымышленный DEMO_EMPLOYER_ID
    await dispatcher.handle(start(CANDIDATE, "demo-prodavec"))
    assert any(b.text == "Откликнуться" for b in buttons(messenger.sent[-1]))
    assert DEMO_EMPLOYER_ID < 0
