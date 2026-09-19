from datetime import UTC, datetime, timedelta

import pytest

from app.services.interviews import SlotError, format_slot, validate_slots
from tests.helpers import buttons, press
from tests.test_applications_api import OWNER, auth, setup


def future(days: int, hour: int) -> str:
    """Локальное время (без пояса) через N дней — так его отправляет мини-приложение."""
    day = datetime.now() + timedelta(days=days)
    return day.replace(hour=hour, minute=0, second=0, microsecond=0).isoformat()


async def invite_anna(api, slots: list[str]):
    apps = (await api.get("/api/vacancies/1/applications", headers=auth())).json()["applications"]
    anna_id = next(a["id"] for a in apps if a["name"] == "Анна")
    return anna_id, await api.post(f"/api/applications/{anna_id}/invite", json={"slots": slots}, headers=auth())


def slot_buttons(message):
    return [b for b in buttons(message) if b.payload.startswith("cand:slot:")]


async def test_full_invitation_flow(session_factory, dispatcher, messenger, api):
    await setup(session_factory, dispatcher, messenger)
    anna_id, resp = await invite_anna(api, [future(2, 11), future(2, 15), future(3, 11)])
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "invited" and len(resp.json()["slots"]) == 3

    invitation = messenger.sent[-1]
    assert invitation.user_id == 101 and "Приглашение на собеседование" in invitation.text
    assert "ул. Примерная" in invitation.text  # адрес
    slots = slot_buttons(invitation)
    assert len(slots) == 3 and slots[0].text.endswith("11:00")

    await dispatcher.handle(press(101, slots[1].payload, name="Анна"))
    confirmation, to_employer = messenger.sent[-2], messenger.sent[-1]
    assert confirmation.user_id == 101 and "записаны на собеседование" in confirmation.text
    assert "15:00" in confirmation.text
    assert to_employer.user_id == OWNER and "Собеседование назначено" in to_employer.text

    # повторный выбор другого слота не меняет запись
    sent = len(messenger.sent)
    await dispatcher.handle(press(101, slots[0].payload, name="Анна"))
    assert len(messenger.sent) == sent
    assert "Время уже выбрано" in messenger.answers[-1].notification

    data = (await api.get("/api/vacancies/1/applications", headers=auth())).json()
    anna = next(a for a in data["applications"] if a["id"] == anna_id)
    assert [s["is_chosen"] for s in anna["slots"]] == [False, True, False]

    await dispatcher.handle(press(101, "cand:my", name="Анна"))
    assert "приглашение на собеседование" in messenger.sent[-1].text and "15:00" in messenger.sent[-1].text


async def test_candidate_declines_all_slots(session_factory, dispatcher, messenger, api):
    await setup(session_factory, dispatcher, messenger)
    anna_id, _ = await invite_anna(api, [future(1, 10), future(1, 12)])
    await dispatcher.handle(press(101, f"cand:noslot:{anna_id}", name="Анна"))
    assert "время не подошло" in messenger.sent[-2].text
    assert messenger.sent[-1].user_id == OWNER and "не подошло время" in messenger.sent[-1].text

    # работодатель предлагает новые варианты — старые кнопки перестают работать
    old = slot_buttons(messenger.sent[-3])
    _, resp = await invite_anna(api, [future(4, 10), future(4, 16)])
    assert resp.status_code == 200
    await dispatcher.handle(press(101, old[0].payload, name="Анна"))
    assert messenger.answers[-1].notification == "Это приглашение больше не действует"


async def test_rejection_cancels_invitation(session_factory, dispatcher, messenger, api):
    await setup(session_factory, dispatcher, messenger)
    anna_id, _ = await invite_anna(api, [future(1, 10), future(1, 12)])
    slots = slot_buttons(messenger.sent[-1])
    await api.patch(f"/api/applications/{anna_id}", json={"status": "rejected"}, headers=auth())
    await dispatcher.handle(press(101, slots[0].payload, name="Анна"))
    assert messenger.answers[-1].notification == "Это приглашение больше не действует"


async def test_other_candidate_cannot_take_slot(session_factory, dispatcher, messenger, api):
    await setup(session_factory, dispatcher, messenger)
    await invite_anna(api, [future(1, 10), future(1, 12)])
    slot = slot_buttons(messenger.sent[-1])[0]
    await dispatcher.handle(press(102, slot.payload, name="Борис"))
    assert messenger.answers[-1].notification == "Это приглашение больше не действует"


async def test_invite_validation(session_factory, dispatcher, messenger, api):
    await setup(session_factory, dispatcher, messenger)
    _, resp = await invite_anna(api, [future(1, 10)])
    assert resp.status_code == 422 and "от 2 до 3" in resp.json()["detail"]["message"]
    _, resp = await invite_anna(api, [future(-1, 10), future(1, 10)])
    assert resp.status_code == 422 and "уже прошло" in resp.json()["detail"]["message"]
    _, resp = await invite_anna(api, [future(1, 10), future(1, 10)])
    assert resp.status_code == 422 and "не должно повторяться" in resp.json()["detail"]["message"]
    # отклонённое приглашение ничего не отправило кандидату
    assert not any("Приглашение" in m.text for m in messenger.sent)


def test_validate_slots_timezone():
    now = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
    # 18:00 по Москве = 15:00 UTC
    slots = validate_slots([datetime(2026, 9, 20, 18, 0), datetime(2026, 9, 21, 9, 30)], now=now)
    assert slots[0] == datetime(2026, 9, 20, 15, 0, tzinfo=UTC)
    assert format_slot(slots[0]) == "вс, 20 сентября, 18:00"
    with pytest.raises(SlotError):
        validate_slots([now + timedelta(days=61), now + timedelta(days=62)], now=now)
