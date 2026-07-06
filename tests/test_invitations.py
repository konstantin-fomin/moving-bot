import pytest

from app.services.invitations import build_invite_link


@pytest.mark.asyncio
async def test_owner_can_create_one_time_invitation(db):
    owner = await db.create_owner_if_first(telegram_id=1, name="Анна")
    invitation = await db.create_invitation(owner.id)

    member = await db.consume_invitation(
        invitation.code,
        telegram_id=2,
        name="Борис",
    )
    second_attempt = await db.consume_invitation(
        invitation.code,
        telegram_id=3,
        name="Вера",
    )

    assert member is not None
    assert member.role == "member"
    assert second_attempt is None
    assert await db.get_user_by_telegram_id(3) is None


@pytest.mark.asyncio
async def test_invalid_invitation_is_rejected(db):
    await db.create_owner_if_first(telegram_id=1, name="Анна")

    member = await db.consume_invitation(
        "wrong-code",
        telegram_id=2,
        name="Борис",
    )

    assert member is None
    assert await db.get_user_by_telegram_id(2) is None


def test_invitation_link_uses_bot_username():
    assert build_invite_link("abc123") == "https://t.me/Moving_GE_bot?start=abc123"
