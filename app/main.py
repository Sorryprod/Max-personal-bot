import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api import applications as applications_api
from app.api import errors as api_errors
from app.api import vacancies as vacancies_api
from app.bot.router import COMMAND_MENU, Dispatcher
from app.db import seed
from app.config import Settings, get_settings
from app.db.session import make_engine, make_session_factory
from app.max import webhook
from app.max.client import MaxApiError, MaxClient
from app.max.poller import run_polling
from app.max.updates import UPDATE_TYPES
from app.services.applinks import AppLinks

log = logging.getLogger(__name__)

WEBHOOK_PATH = "/max/webhook"


async def _setup_updates(settings: Settings, client: MaxClient) -> None:
    """Вебхук и long polling в MAX взаимоисключающие — приводим подписки к выбранному режиму."""
    webhook_url = f"{settings.public_url}{WEBHOOK_PATH}"
    for sub in await client.list_subscriptions():
        if settings.updates_mode == "polling" or sub.get("url") != webhook_url:
            await client.unsubscribe(sub["url"])
            log.info("Снята подписка %s", sub.get("url"))
    if settings.updates_mode == "webhook":
        await client.subscribe(webhook_url, settings.webhook_secret, UPDATE_TYPES)
        log.info("Вебхук подписан: %s", webhook_url)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    engine = make_engine(settings.database_url)
    client = MaxClient(
        settings.bot_token,
        settings.max_api_url,
        timeout=settings.max_api_timeout,
        extra_ca_file=settings.max_extra_ca_file,
        bot_username=settings.bot_username,
    )
    app.state.session_factory = make_session_factory(engine)
    app.state.messenger = client
    app.state.links = AppLinks(settings, client)
    app.state.dispatcher = Dispatcher(app.state.session_factory, client, app.state.links)

    if settings.seed_demo:
        async with app.state.session_factory() as session, session.begin():
            await seed.seed(session)

    poller: asyncio.Task[None] | None = None
    try:
        if not client.bot_username:
            client.bot_username = (await client.get_me()).get("username", "")
        log.info(
            "Бот @%s, апдейты: %s, мини-приложение: %s",
            client.bot_username, settings.updates_mode, settings.webapp_open_mode,
        )
        await _setup_updates(settings, client)
    except MaxApiError:
        log.exception("MAX API недоступен при старте — проверьте BOT_TOKEN и сеть")
    try:
        await client.set_commands(COMMAND_MENU)
    except MaxApiError:
        log.warning("Не удалось зарегистрировать меню команд бота", exc_info=True)
    if settings.updates_mode == "polling":
        poller = asyncio.create_task(run_polling(client, app.state.dispatcher))

    yield

    if poller:
        poller.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await poller
    await client.aclose()
    await engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # httpx логирует каждый long-poll запрос — оставляем только проблемы.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    app = FastAPI(title="MAX hiring bot", lifespan=lifespan)
    app.state.settings = settings
    app.include_router(webhook.router)
    app.include_router(vacancies_api.router)
    app.include_router(applications_api.router)
    api_errors.install(app)

    @app.get("/health", include_in_schema=False)
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    if settings.webapp_dist.is_dir():
        app.mount("/app", StaticFiles(directory=settings.webapp_dist, html=True), name="webapp")

        @app.get("/", include_in_schema=False)
        async def root() -> RedirectResponse:
            return RedirectResponse("/app/")

    return app


app = create_app()
