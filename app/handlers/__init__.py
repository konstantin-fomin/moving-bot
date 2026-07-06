from aiogram import Dispatcher

from app.handlers import checklist, errors, invitations, start


def setup_routers(dispatcher: Dispatcher) -> None:
    dispatcher.include_router(start.router)
    dispatcher.include_router(invitations.router)
    dispatcher.include_router(checklist.router)
    dispatcher.include_router(errors.router)
