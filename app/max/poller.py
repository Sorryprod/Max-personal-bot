"""Long polling через GET /updates — режим без публичного HTTPS-адреса."""

import asyncio
import logging

from app.bot.router import Dispatcher
from app.max.client import MaxApiError, MaxClient
from app.max.updates import parse_update

log = logging.getLogger(__name__)


async def run_polling(client: MaxClient, dispatcher: Dispatcher) -> None:
    marker: int | None = None
    backoff = 1.0
    log.info("Long polling запущен")
    while True:
        try:
            data = await client.get_updates(marker)
        except asyncio.CancelledError:
            raise
        except MaxApiError:
            log.warning("GET /updates не удался, повтор через %.0f с", backoff, exc_info=True)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)
            continue
        backoff = 1.0
        for raw in data.get("updates", []):
            event = parse_update(raw)
            if event is None:
                continue
            try:
                await dispatcher.handle(event)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Не удалось обработать апдейт %s", event.key)
        marker = data.get("marker", marker)
