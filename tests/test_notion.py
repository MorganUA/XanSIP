"""Unit tests: Notion properties and config."""
from services.notion import notion_props
from bot.services.notion_config import DEFAULTS, env_defaults, is_notion_active


def test_title_property():
    prop = notion_props.title("Hello")
    assert prop["title"][0]["text"]["content"] == "Hello"


def test_select_property():
    prop = notion_props.select("Done")
    assert prop["select"]["name"] == "Done"


def test_paragraph_block():
    block = notion_props.paragraph_block("Line")
    assert block["type"] == "paragraph"
    assert block["paragraph"]["rich_text"][0]["text"]["content"] == "Line"


def test_env_defaults_structure():
    cfg = env_defaults()
    assert "databases" in cfg
    assert "sync_events" in cfg
    assert cfg["sync_events"]["ticket_new"] is False


def test_is_notion_active_requires_token(monkeypatch):
    monkeypatch.setattr("bot.services.notion_config.settings.notion_enabled", True)
    monkeypatch.setattr("bot.services.notion_config.settings.notion_api_token", "")
    assert is_notion_active({"enabled": True}) is False

    monkeypatch.setattr("bot.services.notion_config.settings.notion_api_token", "secret")
    assert is_notion_active({"enabled": False}) is True
