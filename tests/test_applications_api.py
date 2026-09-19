from app.db.seed import seed
from tests.helpers import buttons, contact, press, start, text
from tests.test_init_data import make_init_data

OWNER = 2002


def auth(user_id: int = OWNER) -> dict[str, str]:
    return {"X-Init-Data": make_init_data(user_id=user_id)}


async def apply(dispatcher, messenger, user_id: int, name: str, answers: list[str], phone: str) -> None:
    def payload(label: str) -> str:
        return next(b.payload for b in buttons(messenger.sent[-1]) if b.text == label)

    await dispatcher.handle(start(user_id, "demo-povar", name=name))
    await dispatcher.handle(press(user_id, payload("Откликнуться"), name=name))
    for label in answers:
        await dispatcher.handle(press(user_id, payload(label), name=name))
    await dispatcher.handle(text(user_id, name, name=name))
    await dispatcher.handle(contact(user_id, phone, name=name))


async def setup(session_factory, dispatcher, messenger) -> None:
    async with session_factory() as session, session.begin():
        await seed(session, owner_max_id=OWNER, with_candidates=False)
    await apply(dispatcher, messenger, 101, "Анна", ["Да", "Нет", "Больше года"], "79990000001")  # не прошла
    await apply(dispatcher, messenger, 102, "Борис", ["Да", "Да", "До 1 года"], "79990000002")
    # незаконченный отклик не показывается работодателю
    await dispatcher.handle(start(103, "demo-povar", name="Вера"))
    await dispatcher.handle(press(103, next(b.payload for b in buttons(messenger.sent[-1])), name="Вера"))


async def test_list_for_comparison(session_factory, dispatcher, messenger, api):
    await setup(session_factory, dispatcher, messenger)
    resp = await api.get("/api/vacancies/1/applications", headers=auth())
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert [q["text"] for q in data["vacancy"]["questions"]][0] == "Вам есть 18 лет?"
    # прошедший отсев — выше; незаконченный отклик Веры не виден
    assert [a["name"] for a in data["applications"]] == ["Борис", "Анна"]
    anna = data["applications"][1]
    assert anna["screening_failed"] is True and anna["contact"] == "+79990000001"
    medbook = next(a for a in anna["answers"] if a["question_id"] == 2)
    assert (medbook["display"], medbook["passed"]) == ("Нет", False)

    listed = (await api.get("/api/vacancies", headers=auth())).json()
    povar = next(v for v in listed if v["id"] == 1)
    assert (povar["total"], povar["unreviewed"]) == (2, 2)


async def test_status_change_notifies_candidate(session_factory, dispatcher, messenger, api):
    await setup(session_factory, dispatcher, messenger)
    apps = (await api.get("/api/vacancies/1/applications", headers=auth())).json()["applications"]
    anna_id = next(a["id"] for a in apps if a["name"] == "Анна")

    resp = await api.patch(f"/api/applications/{anna_id}", json={"status": "rejected"}, headers=auth())
    assert resp.status_code == 200 and resp.json()["status"] == "rejected"
    assert messenger.sent[-1].user_id == 101 and "выбрал другого кандидата" in messenger.sent[-1].text

    sent = len(messenger.sent)
    await api.patch(f"/api/applications/{anna_id}", json={"status": "rejected"}, headers=auth())
    assert len(messenger.sent) == sent  # повтор без изменений — без повторного уведомления

    await api.patch(f"/api/applications/{anna_id}", json={"status": "reserve"}, headers=auth())
    assert "в резерв" in messenger.sent[-1].text

    # кандидат видит актуальный статус в «Мои отклики»
    await dispatcher.handle(press(101, "cand:my", name="Анна"))
    assert "в резерве" in messenger.sent[-1].text

    listed = (await api.get("/api/vacancies", headers=auth())).json()
    assert next(v for v in listed if v["id"] == 1)["unreviewed"] == 1


async def test_bad_status_and_foreign_access(session_factory, dispatcher, messenger, api):
    await setup(session_factory, dispatcher, messenger)
    app_id = (await api.get("/api/vacancies/1/applications", headers=auth())).json()["applications"][0]["id"]
    resp = await api.patch(f"/api/applications/{app_id}", json={"status": "hired"}, headers=auth())
    assert resp.status_code == 422

    await dispatcher.handle(press(4004, "role:employer"))
    await dispatcher.handle(text(4004, "Магазин"))
    await dispatcher.handle(text(4004, "Валуйки"))
    resp = await api.patch(f"/api/applications/{app_id}", json={"status": "rejected"}, headers=auth(4004))
    assert resp.status_code == 404
    resp = await api.get("/api/vacancies/1/applications", headers=auth(4004))
    assert resp.status_code == 404
