from aiogram import Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message

from app.database import Database, User
from app.handlers.common import ACCESS_DENIED_TEXT
from app.keyboards import main_menu_keyboard


router = Router(name="start")


@router.message(CommandStart())
async def start_command(message: Message, command: CommandObject, db: Database) -> None:
    if message.from_user is None:
        return

    telegram_id = message.from_user.id
    name = message.from_user.full_name
    existing_user = await db.get_user_by_telegram_id(telegram_id)
    if existing_user is not None:
        await message.answer("Главное меню открыто.", reply_markup=main_menu_keyboard())
        return

    invite_code = _start_payload(message, command)
    if invite_code:
        invited_user = await db.consume_invitation(invite_code, telegram_id, name)
        if invited_user is not None:
            await message.answer(
                _member_welcome_text(),
                reply_markup=main_menu_keyboard(),
            )
            return

    owner = await db.create_owner_if_first(telegram_id, name)
    if owner is not None:
        await message.answer(_owner_welcome_text(), reply_markup=main_menu_keyboard())
        return

    await message.answer(ACCESS_DENIED_TEXT)


@router.message(Command("help"))
async def help_command(message: Message, db: Database) -> None:
    if message.from_user is None:
        return

    user = await db.get_user_by_telegram_id(message.from_user.id)
    if user is None:
        await message.answer(ACCESS_DENIED_TEXT)
        return

    await message.answer(_help_text(user), reply_markup=main_menu_keyboard())


def _owner_welcome_text() -> str:
    return (
        "Добро пожаловать в помощник переезда.\n\n"
        "Вы стали владельцем общего списка. Пишите вещи обычным текстом: "
        "что купить, что взять или что важно не забыть.\n\n"
        "Чтобы пригласить партнёра, отправьте команду /invite."
    )


def _member_welcome_text() -> str:
    return (
        "Добро пожаловать в общий список переезда.\n\n"
        "Теперь вы можете добавлять вещи, отмечать выполненное и смотреть общий список."
    )


def _start_payload(message: Message, command: CommandObject) -> str:
    if command.args:
        return command.args.strip()

    if not message.text:
        return ""

    parts = message.text.strip().split(maxsplit=1)
    if len(parts) != 2:
        return ""

    return parts[1].strip()


def _help_text(user: User) -> str:
    owner_hint = (
        "\n\nВы владелец: отправьте /invite, чтобы создать одноразовую ссылку для партнёра."
        if user.role == "owner"
        else ""
    )
    return (
        "Пишите мне обычным текстом список вещей для переезда. "
        "Можно несколько пунктов сразу и можно со ссылками на магазины.\n\n"
        "Примеры:\n"
        "• купить коробки и скотч\n"
        "• взять зимние куртки\n"
        "• готово с подгузниками\n\n"
        "Кнопки показывают покупки, вещи, важное, весь список и откат последнего действия."
        f"{owner_hint}"
    )
