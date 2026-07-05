"""Tests: SIP integration guides content."""
from services.sip_integration_guides import get_sip_integration_guides, GUIDES


def test_guides_loaded():
    data = get_sip_integration_guides()
    assert len(data["guides"]) >= 6
    assert "disclaimer" in data
    assert "mor5" in data["categories"]


def test_all_guides_have_kolmisoft_sources():
    for g in GUIDES:
        assert g.get("steps"), f"{g['id']} has no steps"
        sources = g.get("sources") or []
        assert sources, f"{g['id']} has no sources"
        for src in sources:
            url = src["url"]
            assert "kolmisoft.com" in url or "3cx.com" in url, url
