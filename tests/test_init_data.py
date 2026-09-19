import json
import time
from urllib.parse import quote, urlencode

import pytest

from app.api.auth import InitDataError, sign_init_data, validate_init_data

TOKEN = "test-token"


def make_init_data(user_id: int = 42, auth_date: int | None = None, token: str = TOKEN, **extra: str) -> str:
    fields = {
        "auth_date": str(auth_date or int(time.time())),
        "query_id": "q1",
        "user": json.dumps({"id": user_id, "first_name": "Иван", "last_name": "Работодатель"}, ensure_ascii=False),
        **extra,
    }
    fields["hash"] = sign_init_data(fields, token)
    return urlencode(fields)


def test_valid_init_data():
    user = validate_init_data(make_init_data(user_id=7), TOKEN, ttl_seconds=3600)
    assert user.id == 7 and user.full_name == "Иван Работодатель"


def test_start_param_is_signed_too():
    user = validate_init_data(make_init_data(start_param="new"), TOKEN, ttl_seconds=3600)
    assert user.id == 42


def test_wrapped_in_webappdata_fragment():
    raw = "#WebAppData=" + quote(make_init_data(user_id=9))
    assert validate_init_data(raw, TOKEN, ttl_seconds=3600).id == 9


def test_signed_with_other_token_rejected():
    with pytest.raises(InitDataError):
        validate_init_data(make_init_data(token="other-token"), TOKEN, ttl_seconds=3600)


def test_tampered_user_id_rejected():
    forged = make_init_data(user_id=1).replace("%22id%22%3A+1", "%22id%22%3A+2")
    assert forged != make_init_data(user_id=1)
    with pytest.raises(InitDataError):
        validate_init_data(forged, TOKEN, ttl_seconds=3600)


def test_expired_rejected():
    old = make_init_data(auth_date=int(time.time()) - 7200)
    with pytest.raises(InitDataError):
        validate_init_data(old, TOKEN, ttl_seconds=3600)


@pytest.mark.parametrize("raw", ["", "user=%7B%7D", "hash=abc"])
def test_garbage_rejected(raw):
    with pytest.raises(InitDataError):
        validate_init_data(raw, TOKEN, ttl_seconds=3600)


async def test_api_requires_signature(api):
    resp = await api.get("/api/me")
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "unauthorized"
    resp = await api.get("/api/me", headers={"X-Init-Data": make_init_data(token="other")})
    assert resp.status_code == 401
