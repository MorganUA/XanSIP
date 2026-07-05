"""Tests: operation guides content."""
from services.operation_guides import (
    AUDIENCES,
    GUIDES,
    format_guide_html,
    get_guide_by_id,
    get_operation_guides,
    guides_for_audience,
)


def test_audiences_defined():
    assert set(AUDIENCES.keys()) == {"workflow", "user", "group_owner", "admin"}


def test_featured_workflow_guide():
    data = get_operation_guides()
    assert data["featured_guide_id"] == "workflow-max-value"
    assert len(data["workflow_roadmap"]) == 4
    g = get_guide_by_id("workflow-max-value")
    assert g and g["audience"] == "workflow"


def test_guides_per_audience():
    data = get_operation_guides()
    assert len(data["guides"]) >= 16
    for aud in ("workflow", "user", "group_owner", "admin"):
        assert len(guides_for_audience(aud)) >= 3, aud
    admin_ids = {g["id"] for g in guides_for_audience("admin")}
    assert "admin-web-accounts" in admin_ids


def test_admin_web_accounts_guide():
    g = get_guide_by_id("admin-web-accounts")
    assert g and g["audience"] == "admin"
    assert "admin01" in g["summary"] or any("admin01" in s.get("body", "") for s in g["steps"])
    assert "support01" in "".join(s.get("body", "") for s in g["steps"])
    assert "roof" in "".join(s.get("body", "") for s in g["steps"])


def test_each_guide_has_steps():
    for g in GUIDES:
        assert g.get("steps"), g["id"]
        assert g.get("title") and g.get("summary")


def test_get_guide_by_id():
    g = get_guide_by_id("user-tickets")
    assert g and g["audience"] == "user"


def test_format_guide_html():
    g = get_guide_by_id("admin-webcrm")
    html = format_guide_html(g)
    assert "Web CRM" in html
    assert "<b>" in html
