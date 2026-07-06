import pytest

from app.database import Database


@pytest.fixture
async def db(tmp_path):
    database = Database(tmp_path / "bot.db")
    await database.connect()
    await database.init_schema()
    try:
        yield database
    finally:
        await database.close()
