from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATABASE_PATH = BASE_DIR / "data" / "bot.db"
BOT_USERNAME = "Moving_GE_bot"
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"
DEFAULT_TZ = "Etc/UTC"


@dataclass(frozen=True)
class Config:
    bot_token: str
    gemini_api_key: str
    gemini_model: str
    timezone: str
    database_path: Path
    bot_username: str = BOT_USERNAME


def load_config() -> Config:
    load_dotenv(BASE_DIR / ".env")

    token = os.getenv("BOT_TOKEN", "").strip()
    if not _looks_like_bot_token(token):
        raise RuntimeError("BOT_TOKEN не найден или имеет неверный формат в .env")

    gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY не найден в .env")

    gemini_model = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip()
    timezone = os.getenv("TZ", DEFAULT_TZ).strip() or DEFAULT_TZ

    return Config(
        bot_token=token,
        gemini_api_key=gemini_api_key,
        gemini_model=gemini_model,
        timezone=timezone,
        database_path=DEFAULT_DATABASE_PATH,
    )


def _looks_like_bot_token(token: str) -> bool:
    left, sep, right = token.partition(":")
    return bool(sep and left.isdigit() and right)
