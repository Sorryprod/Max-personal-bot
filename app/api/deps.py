from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import WebAppUser
from app.db.models import Employer
from app.messaging import Outbox, flush_outbox
from app.services import vacancies


@asynccontextmanager
async def unit_of_work(request: Request) -> AsyncIterator[tuple[AsyncSession, Outbox]]:
    """Транзакция + исходящие сообщения, которые уходят только после успешного коммита."""
    outbox = Outbox()
    async with request.app.state.session_factory() as session, session.begin():
        yield session, outbox
    await flush_outbox(request.app.state.messenger, outbox)


def api_error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


async def require_employer(session: AsyncSession, user: WebAppUser) -> Employer:
    employer = await vacancies.get_employer(session, user.id)
    if employer is None or not employer.place_name:
        raise api_error(
            409,
            "employer_not_registered",
            "Сначала откройте бота, выберите «Я ищу сотрудников» и укажите название точки.",
        )
    return employer
