from sqlalchemy import func, select

from app.db.models import Application, ApplicationStatus, Candidate, DialogState, Employer, Vacancy
from app.db.seed import DEMO_CANDIDATES, reset, seed
from tests.helpers import buttons, contact, press, start, text
from tests.test_applications_api import OWNER, apply, auth, setup
from tests.test_employer_flow import VACANCY
from tests.test_interviews import future


async def count(session_factory, model, *where) -> int:
    async with session_factory() as session:
        return await session.scalar(select(func.count()).select_from(model).where(*where))


async def test_consent_shown_and_recorded(session_factory, dispatcher, messenger):
    async with session_factory() as session, session.begin():
        await seed(session, owner_max_id=OWNER, with_candidates=False)
    await dispatcher.handle(start(101, "demo-povar", name="Анна"))
    await dispatcher.handle(press(101, buttons(messenger.sent[-1])[0].payload, name="Анна"))
    for label in ("Да", "Да", "Нет опыта"):
        await dispatcher.handle(press(101, next(b.payload for b in buttons(messenger.sent[-1]) if b.text == label)))
    await dispatcher.handle(text(101, "Анна"))
    assert "соглашаетесь на передачу" in messenger.sent[-1].text
    async with session_factory() as session:
        assert (await session.scalar(select(Candidate))).consent_at is None
    await dispatcher.handle(contact(101, "79990000001"))
    async with session_factory() as session:
        assert (await session.scalar(select(Candidate))).consent_at is not None


async def test_privacy_command_works_mid_flow(session_factory, dispatcher, messenger):
    async with session_factory() as session, session.begin():
        await seed(session, owner_max_id=OWNER, with_candidates=False)
    await dispatcher.handle(start(101, "demo-povar"))
    await dispatcher.handle(press(101, buttons(messenger.sent[-1])[0].payload))
    await dispatcher.handle(text(101, "/privacy"))
    assert "Какие данные хранит бот" in messenger.sent[-1].text


async def test_candidate_deletes_data(session_factory, dispatcher, messenger, api):
    await setup(session_factory, dispatcher, messenger)
    await dispatcher.handle(text(101, "/delete"))
    assert "отклики (1)" in messenger.sent[-1].text
    await dispatcher.handle(press(101, "acc:keep"))
    assert await count(session_factory, Candidate, Candidate.max_user_id == 101) == 1

    await dispatcher.handle(text(101, "/delete"))
    await dispatcher.handle(press(101, "acc:delete"))
    assert "данные удалены" in messenger.sent[-1].text
    assert await count(session_factory, Candidate, Candidate.max_user_id == 101) == 0
    assert await count(session_factory, DialogState, DialogState.max_user_id == 101) == 0
    names = [a["name"] for a in (await api.get("/api/vacancies/1/applications", headers=auth())).json()["applications"]]
    assert names == ["Борис"]

    await dispatcher.handle(text(101, "/delete"))
    assert "удалять нечего" in messenger.sent[-1].text


async def test_employer_deletes_data(session_factory, dispatcher, messenger, api):
    await setup(session_factory, dispatcher, messenger)
    anna_id = (await api.get("/api/vacancies/1/applications", headers=auth())).json()["applications"][1]["id"]
    await api.post(f"/api/applications/{anna_id}/invite", json={"slots": [future(1, 10), future(1, 12)]},
                   headers=auth())
    await dispatcher.handle(text(OWNER, "/delete"))
    assert "вакансии (2)" in messenger.sent[-1].text
    await dispatcher.handle(press(OWNER, "acc:delete"))
    assert await count(session_factory, Employer, Employer.max_user_id == OWNER) == 0
    assert await count(session_factory, Vacancy) == 0
    assert await count(session_factory, Application) == 0
    # кандидаты как люди остаются — их данные удаляются только по их собственному запросу
    assert await count(session_factory, Candidate, Candidate.max_user_id == 101) == 1
    resp = await api.get("/api/vacancies", headers=auth())
    assert resp.status_code == 409


async def test_example_vacancy_for_new_employer(session_factory, dispatcher, messenger, api):
    async with session_factory() as session, session.begin():
        await seed(session)  # демо-кандидаты должны существовать заранее
    await dispatcher.handle(press(3003, "role:employer", name="Иван"))
    await dispatcher.handle(text(3003, "Кафе", name="Иван"))
    await dispatcher.handle(text(3003, "Белгород", name="Иван"))
    example = next(b for b in buttons(messenger.sent[-1]) if b.text == "Посмотреть на примере")

    await dispatcher.handle(press(3003, example.payload, name="Иван"))
    assert "вымышленными кандидатами" in messenger.sent[-1].text
    listed = (await api.get("/api/vacancies", headers=auth(3003))).json()
    assert [v["position"] for v in listed] == ["Повар горячего цеха (пример)"]
    assert listed[0]["total"] == sum(1 for c in DEMO_CANDIDATES if c[0] == "demo-povar")

    await dispatcher.handle(press(3003, example.payload, name="Иван"))  # повторно не создаётся
    assert len((await api.get("/api/vacancies", headers=auth(3003))).json()) == 1

    # после первой вакансии кнопка примера из меню пропадает
    await dispatcher.handle(press(3003, "role:employer", name="Иван"))
    assert all(b.text != "Посмотреть на примере" for b in buttons(messenger.sent[-1]))


async def test_reset_restores_demo_and_keeps_real_data(session_factory, dispatcher, messenger, api):
    async with session_factory() as session, session.begin():
        await seed(session, owner_max_id=OWNER)
    # реальная вакансия работодателя и изменения в демо-данных
    await dispatcher.handle(press(OWNER, "role:employer"))
    await api.post("/api/vacancies", json=VACANCY, headers=auth())
    irina = next(a for a in (await api.get("/api/vacancies/1/applications", headers=auth())).json()["applications"]
                 if a["name"] == "Ирина Соколова")
    await api.patch(f"/api/applications/{irina['id']}", json={"status": "rejected"}, headers=auth())

    async with session_factory() as session, session.begin():
        await reset(session)
        await seed(session, owner_max_id=OWNER)

    positions = sorted(v["position"] for v in (await api.get("/api/vacancies", headers=auth())).json())
    assert positions == ["Официант", "Повар горячего цеха", "Продавец-кассир"]
    async with session_factory() as session:
        statuses = set(await session.scalars(select(Application.status)))
    assert statuses == {ApplicationStatus.screened}
    assert await count(session_factory, Application) == len(DEMO_CANDIDATES)


async def test_apply_helper_still_works_with_commands(session_factory, dispatcher, messenger):
    """Регрессия: обычный текст не принимается за команду."""
    async with session_factory() as session, session.begin():
        await seed(session, owner_max_id=OWNER, with_candidates=False)
    await apply(dispatcher, messenger, 101, "Анна", ["Да", "Да", "Нет опыта"], "79990000001")
    assert "Отклик отправлен" in messenger.sent[-2].text or "Отклик отправлен" in messenger.sent[-1].text
