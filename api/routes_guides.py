"""Справочные материалы Web CRM."""

from fastapi import APIRouter, HTTPException, Query

from services.operation_guides import get_guide_by_id, get_operation_guides
from services.sip_integration_guides import get_sip_integration_guides

router = APIRouter(tags=["guides"])


@router.get("/api/guides/sip-integration")
async def sip_integration_guides():
    return get_sip_integration_guides()


@router.get("/api/guides/operations")
async def operation_guides(audience: str | None = Query(None, description="user | group_owner | admin")):
    if audience and audience not in ("user", "group_owner", "admin", "workflow"):
        raise HTTPException(status_code=400, detail="Invalid audience")
    return get_operation_guides(audience=audience)


@router.get("/api/guides/operations/{guide_id}")
async def operation_guide_detail(guide_id: str):
    guide = get_guide_by_id(guide_id)
    if not guide:
        raise HTTPException(status_code=404, detail="Guide not found")
    return guide
