"""Group access and service desk correctness tests."""
from __future__ import annotations

import pytest

from bot.utils.group_access import group_access_error
from db.models.group import Group


def _group(**kwargs) -> Group:
    g = Group(
        telegram_group_id=-1001,
        group_name="Test",
        is_approved=True,
        is_banned=False,
        is_frozen=False,
        is_deleted=False,
    )
    for k, v in kwargs.items():
        setattr(g, k, v)
    return g


def test_group_access_error_frozen():
    g = _group(is_frozen=True, frozen_reason="техработы")
    err = group_access_error(g)
    assert err and "заморожен" in err.lower()


def test_group_access_error_ok():
    assert group_access_error(_group()) is None


def test_service_desk_rejects_frozen_group():
    pytest.importorskip("asyncpg")
    from unittest.mock import AsyncMock, MagicMock, patch

    from api.services.service_desk import ServiceDeskError, create_group_service_desk_ticket

    frozen = _group(is_frozen=True, frozen_reason="audit")

    async def _run():
        mock_session = AsyncMock()
        with patch("api.services.service_desk.get_group_preset", return_value=MagicMock(label="x", error_type="other")):
            with patch("api.services.service_desk.GroupRepository") as grp_cls:
                grp_cls.return_value.get_by_telegram_id = AsyncMock(return_value=frozen)
                with pytest.raises(ServiceDeskError) as exc:
                    await create_group_service_desk_ticket(
                        mock_session,
                        AsyncMock(),
                        sip_number="100",
                        error_preset_id="gd_fraud",
                        initiator_telegram_id=1,
                        group_chat_id=-1001,
                    )
                assert exc.value.status_code == 403
                assert "frozen" in str(exc.value).lower()

    import asyncio
    asyncio.run(_run())
