"""Phase 3 architecture smoke tests."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_core_config_shim():
    from bot.config import settings as bot_settings
    from core.config import settings as core_settings

    assert bot_settings is core_settings


def test_api_routers_package():
    routers_dir = ROOT / "api" / "routers"
    expected = {
        "pages.py", "auth.py", "dashboard.py", "notifications.py",
        "users.py", "sips.py", "tickets.py", "groups.py",
    }
    assert expected <= {p.name for p in routers_dir.iterdir() if p.suffix == ".py"}


def test_main_is_slim():
    lines = (ROOT / "api" / "main.py").read_text(encoding="utf-8").splitlines()
    assert len(lines) < 120


def test_guides_json_bundles():
    guides_dir = ROOT / "data" / "guides"
    assert (guides_dir / "operations.json").is_file()
    assert (guides_dir / "sip-integration.json").is_file()


def test_guides_load_from_json():
    from services.operation_guides import GUIDES, get_operation_guides
    from services.sip_integration_guides import get_sip_integration_guides

    assert len(GUIDES) >= 10
    assert "guides" in get_operation_guides()
    assert "guides" in get_sip_integration_guides()


def test_notification_config_shim_source():
    text = (ROOT / "bot" / "services" / "notification_config.py").read_text(encoding="utf-8")
    assert "core.notification_config" in text
