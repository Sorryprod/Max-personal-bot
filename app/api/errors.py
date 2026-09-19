from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

FIELD_LABELS = {
    "position": "Должность",
    "schedule": "График",
    "salary_from": "Зарплата от",
    "salary_to": "Зарплата до",
    "address": "Адрес",
    "questions": "Вопросы",
    "text": "Текст вопроса",
    "options": "Варианты ответа",
    "accepted": "Подходящие ответы",
    "status": "Статус",
    "slots": "Время собеседования",
}


def install(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        messages = []
        for err in exc.errors():
            msg = err.get("msg", "")
            if msg.startswith("Value error, "):  # наши сообщения из валидаторов — уже по-русски
                messages.append(msg[len("Value error, ") :])
                continue
            field = next((FIELD_LABELS[p] for p in reversed(err.get("loc", ())) if p in FIELD_LABELS), None)
            messages.append(f"Проверьте поле «{field}»" if field else "Проверьте заполнение формы")
        message = "; ".join(dict.fromkeys(messages)) or "Проверьте заполнение формы"
        return JSONResponse(status_code=422, content={"detail": {"code": "validation", "message": message}})
