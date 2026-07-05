"""Unit tests: notification config merge/normalize."""
from bot.services.notification_config import (
    merge_config,
    normalize_config,
    replace_chat_id,
    support_action_chat_ids,
    DEFAULT_EVENTS,
)


def test_merge_empty_uses_structure():
    cfg = merge_config(None)
    assert "support_chat_ids" in cfg
    assert "admin_chat_ids" in cfg
    assert cfg["events"]["ticket_new"]["support_chats"] is True


def test_merge_stored_overrides_lists():
    stored = {
        "support_chat_ids": [-100111, -100222],
        "admin_chat_ids": [999],
        "events": {"ticket_new": {"support_chats": False}},
    }
    cfg = merge_config(stored)
    assert cfg["support_chat_ids"] == [-100111, -100222]
    assert cfg["admin_chat_ids"] == [999]
    assert cfg["events"]["ticket_new"]["support_chats"] is False
    assert cfg["events"]["ticket_status"]["user_dm"] is True


def test_normalize_dedupes_ids():
    cfg = normalize_config({
        "support_chat_ids": [1, 1, 2],
        "admin_chat_ids": [3],
        "events": DEFAULT_EVENTS,
    })
    assert cfg["support_chat_ids"] == [1, 2]


def test_support_action_chat_ids_union():
    cfg = {"support_chat_ids": [1, 2], "admin_chat_ids": [2, 3]}
    assert support_action_chat_ids(cfg) == {1, 2, 3}
