from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.database import Database
from app.handlers.common import ACCESS_DENIED_TEXT
from app.services.invitations import build_invite_link


router = Router(name="invitations")


@router.message(Command("invite"))
async def invite_partner(message: Message, db: Database) -> None:
    if message.from_user is None:
        return

    user = await db.get_user_by_telegram_id(message.from_user.id)
    if user is None:
        await message.answer(ACCESS_DENIED_TEXT)
        return

    if user.role != "owner":
        await message.answer("Приглашение может создать только владелец.")
        return

    invitation = await db.create_invitation(user.id)
    link = build_invite_link(invitation.code)
    await message.answer(
        "Готово, вот одноразовая ссылка для партнёра:\n\n"
        f"{link}\n\n"
        "После первого входа ссылка станет недействительной."
    )
