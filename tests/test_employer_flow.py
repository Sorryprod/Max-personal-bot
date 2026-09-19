from sqlalchemy import select

from app.db.models import Employer, Vacancy
from tests.helpers import buttons, press, start, text
from tests.test_init_data import make_init_data

EMPLOYER = 3003


def auth(user_id: int = EMPLOYER) -> dict[str, str]:
    return {"X-Init-Data": make_init_data(user_id=user_id)}


VACANCY = {
    "position": "Официант",
    "schedule": "2/2, 10:00–22:00",
    "salary_from": 40000,
    "salary_to": 55000,
    "address": "Белгород, пр. Славы, 10",
    "questions": [
        {"text": "Вам есть 18 лет?", "qtype": "yes_no", "is_blocking": True, "accepted": ["yes"]},
        {"text": "Опыт работы", "qtype": "choice", "options": ["Нет", "Есть"], "is_blocking": False},
    ],
}


async def register_employer(dispatcher, messenger) -> None:
    await dispatcher.handle(start(EMPLOYER, name="Иван"))
    await dispatcher.handle(press(EMPLOYER, "role:employer", name="Иван"))
    assert "Как называется" in messenger.sent[-1].text
    await dispatcher.handle(text(EMPLOYER, "К", name="Иван"))  # слишком коротко
    assert "от 2 до 100" in messenger.sent[-1].text
    await dispatcher.handle(text(EMPLOYER, "Кафе «Ромашка»", name="Иван"))
    city = next(b for b in buttons(messenger.sent[-1]) if b.text == "Губкин")
    await dispatcher.handle(press(EMPLOYER, city.payload, name="Иван"))


async def test_employer_registration_in_chat(dispatcher, messenger, session_factory):
    await register_employer(dispatcher, messenger)
    menu = messenger.sent[-1]
    assert "Кафе «Ромашка»" in menu.text and "Губкин" in menu.text
    labels = [b.text for b in buttons(menu)]
    assert "Создать вакансию" in labels and "Мои вакансии и кандидаты" in labels
    async with session_factory() as session:
        employer = await session.scalar(select(Employer))
    assert (employer.max_user_id, employer.place_name, employer.city) == (EMPLOYER, "Кафе «Ромашка»", "Губкин")

    # повторный выбор роли сразу показывает меню
    await dispatcher.handle(press(EMPLOYER, "role:employer", name="Иван"))
    assert "Кафе «Ромашка»" in messenger.sent[-1].text


async def test_create_vacancy_sends_invite_link(dispatcher, messenger, api, session_factory):
    await register_employer(dispatcher, messenger)
    resp = await api.post("/api/vacancies", json=VACANCY, headers=auth())
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["invite_link"].startswith("https://max.ru/test_bot?start=")
    assert len(body["questions"]) == 2

    published = messenger.sent[-1]
    assert published.user_id == EMPLOYER
    assert body["invite_link"] in published.text
    assert any(b.payload == body["invite_link"] for b in buttons(published))

    # кандидат проходит по ссылке — видит карточку новой вакансии
    slug = body["invite_link"].rsplit("=", 1)[1]
    await dispatcher.handle(start(5005, slug))
    assert "Официант" in messenger.sent[-1].text

    listed = (await api.get("/api/vacancies", headers=auth())).json()
    assert [v["position"] for v in listed] == ["Официант"]


async def test_unregistered_employer_gets_hint(api):
    resp = await api.get("/api/vacancies", headers=auth(9999))
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "employer_not_registered"
    me = (await api.get("/api/me", headers=auth(9999))).json()
    assert me["employer"] is None and me["question_templates"]


async def test_vacancy_validation_messages(dispatcher, messenger, api):
    await register_employer(dispatcher, messenger)
    bad = {**VACANCY, "salary_from": 90000, "salary_to": 50000}
    resp = await api.post("/api/vacancies", json=bad, headers=auth())
    assert resp.status_code == 422
    assert "Зарплата «от» больше" in resp.json()["detail"]["message"]

    too_many = {**VACANCY, "questions": VACANCY["questions"] * 2}
    resp = await api.post("/api/vacancies", json=too_many, headers=auth())
    assert resp.status_code == 422 and "Вопросы" in resp.json()["detail"]["message"]

    useless = {**VACANCY, "questions": [{"text": "Есть 18?", "qtype": "yes_no", "is_blocking": True,
                                          "accepted": ["yes", "no"]}]}
    resp = await api.post("/api/vacancies", json=useless, headers=auth())
    assert resp.status_code == 422 and "никого не отсеивает" in resp.json()["detail"]["message"]


async def test_other_employer_cannot_see_vacancy(dispatcher, messenger, api, session_factory):
    await register_employer(dispatcher, messenger)
    vacancy_id = (await api.post("/api/vacancies", json=VACANCY, headers=auth())).json()["id"]
    await dispatcher.handle(press(4004, "role:employer"))
    await dispatcher.handle(text(4004, "Магазин"))
    await dispatcher.handle(text(4004, "Валуйки"))
    resp = await api.get(f"/api/vacancies/{vacancy_id}", headers=auth(4004))
    assert resp.status_code == 404
    resp = await api.patch(f"/api/vacancies/{vacancy_id}", json={"status": "closed"}, headers=auth(4004))
    assert resp.status_code == 404


async def test_closed_vacancy_link_stops_working(dispatcher, messenger, api, session_factory):
    await register_employer(dispatcher, messenger)
    created = (await api.post("/api/vacancies", json=VACANCY, headers=auth())).json()
    resp = await api.patch(f"/api/vacancies/{created['id']}", json={"status": "closed"}, headers=auth())
    assert resp.json()["status"] == "closed"
    async with session_factory() as session:
        slug = await session.scalar(select(Vacancy.invite_slug))
    await dispatcher.handle(start(5005, slug))
    assert "закрыта" in messenger.sent[-1].text
