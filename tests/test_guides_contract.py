"""Contract tests: guides content schema (no TestClient DB)."""
from __future__ import annotations

from services.operation_guides import FEATURED_GUIDE_ID, GUIDES, WORKFLOW_ROADMAP, get_operation_guides
from services.sip_integration_guides import GUIDES as SIP_GUIDES

WEB_SECTIONS = frozenset({
    "dashboard", "service-desk", "users", "sips", "tickets", "groups",
    "finance", "notion", "operation-guides", "sip-guides", "audit", "system", "notifications",
})

REQUIRED_GUIDE_KEYS = frozenset({"id", "title", "summary", "steps", "audience"})


def test_operation_guide_ids_unique():
    ids = [g["id"] for g in GUIDES]
    assert len(ids) == len(set(ids))


def test_sip_guide_ids_unique():
    ids = [g["id"] for g in SIP_GUIDES]
    assert len(ids) == len(set(ids))


def test_operation_guides_schema():
    data = get_operation_guides()
    assert data["featured_guide_id"] == FEATURED_GUIDE_ID
    assert len(data["workflow_roadmap"]) == 4
    assert set(data["audiences"].keys()) == {"workflow", "user", "group_owner", "admin"}
    for g in data["guides"]:
        assert REQUIRED_GUIDE_KEYS <= g.keys(), g["id"]


def test_workflow_roadmap_web_sections_valid():
    for phase in WORKFLOW_ROADMAP:
        assert phase["web_section"] in WEB_SECTIONS, phase["id"]


def test_guide_step_web_sections_valid():
    bad: list[str] = []
    for g in GUIDES:
        for step in g.get("steps") or []:
            ws = step.get("web_section")
            if ws and ws not in WEB_SECTIONS:
                bad.append(f"{g['id']}:{step.get('title')}:{ws}")
    assert not bad, bad
