import hmac
import logging

from fastapi import APIRouter, Header, HTTPException, Request

from app.max.updates import parse_update

log = logging.getLogger(__name__)
router = APIRouter()


@router.post("/max/webhook", include_in_schema=False)
async def max_webhook(
    request: Request,
    x_max_bot_api_secret: str | None = Header(default=None),
) -> dict[str, bool]:
    secret = request.app.state.settings.webhook_secret
    if not secret or not hmac.compare_digest(x_max_bot_api_secret or "", secret):
        raise HTTPException(status_code=401)
    try:
        raw = await request.json()
    except ValueError:
        return {"ok": True}  # мусор не ретраим
    event = parse_update(raw) if isinstance(raw, dict) else None
    if event is not None:
        # Исключение (например, БД недоступна) -> 500 -> MAX доставит апдейт повторно.
        await request.app.state.dispatcher.handle(event)
    return {"ok": True}
