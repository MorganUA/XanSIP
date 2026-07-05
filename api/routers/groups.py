from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session
from api.rbac import get_admin_actor
from api.schemas.admin import BanBody, GroupCreateBody, GroupFreezeBody, GroupOwnerBody, GroupUpdateBody
from api.serializers import user_brief
from api.services.group_present import serialize_group
from api.services import telegram as tg
from bot.utils.admin_audit import log_admin_action
from db.models.group import Group
from db.models.user import User
from db.repositories.group_repo import GroupRepository
from db.repositories.user_repo import UserRepository

router = APIRouter(prefix="/api/groups", tags=["groups"])


async def load_group_item(session: AsyncSession, group: Group) -> dict:
    user_repo = UserRepository(session)
    repo = GroupRepository(session)
    owner = await user_repo.get_by_id(group.owner_user_id) if group.owner_user_id else None
    approver = await user_repo.get_by_id(group.approved_by) if group.approved_by else None
    counts = await repo.count_open_tickets_by_group([group.id])
    return serialize_group(
        group,
        owner=owner,
        approved_by=approver,
        open_tickets=counts.get(group.id, 0),
    )


@router.get("")
async def list_groups(
    session: AsyncSession = Depends(get_session),
    include_deleted: bool = Query(default=False),
):
    repo = GroupRepository(session)
    user_repo = UserRepository(session)
    groups = await repo.get_all(include_deleted=include_deleted)
    ticket_counts = await repo.count_open_tickets_by_group([g.id for g in groups])
    items = []
    for group in groups:
        owner = await user_repo.get_by_id(group.owner_user_id) if group.owner_user_id else None
        approver = await user_repo.get_by_id(group.approved_by) if group.approved_by else None
        items.append(serialize_group(
            group,
            owner=owner,
            approved_by=approver,
            open_tickets=ticket_counts.get(group.id, 0),
        ))
    return {"items": items}


@router.get("/{group_id}")
async def get_group(group_id: int, session: AsyncSession = Depends(get_session)):
    repo = GroupRepository(session)
    group = await repo.get_by_id(group_id, include_deleted=True)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return await load_group_item(session, group)


@router.post("")
async def create_group(
    body: GroupCreateBody,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_admin_actor),
):
    repo = GroupRepository(session)
    user_repo = UserRepository(session)
    existing = await repo.get_by_telegram_id_any(body.telegram_group_id)
    if existing:
        if existing.is_deleted:
            raise HTTPException(
                status_code=409,
                detail="Group with this Telegram ID was deleted. Restore is not supported yet.",
            )
        raise HTTPException(status_code=409, detail="Group with this Telegram ID already exists")
    owner_id = None
    if body.owner_telegram_id:
        owner = await user_repo.get_by_telegram_id(body.owner_telegram_id)
        if not owner:
            raise HTTPException(status_code=404, detail="Owner user not found")
        owner_id = owner.id
    group = await repo.create(
        body.telegram_group_id,
        group_name=body.group_name,
        owner_user_id=owner_id,
        call_center_label=body.call_center_label,
        tariff=body.tariff,
        tariff_notes=body.tariff_notes,
        work_conditions=body.work_conditions,
        participants_info=body.participants_info,
        contact_info=body.contact_info,
        notes=body.notes,
    )
    await log_admin_action(
        session, actor, "create_group",
        entity_type="group", entity_id=group.id,
        new_value={"telegram_group_id": group.telegram_group_id, "source": "web"},
    )
    return await load_group_item(session, group)


@router.patch("/{group_id}")
async def update_group(
    group_id: int,
    body: GroupUpdateBody,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_admin_actor),
):
    repo = GroupRepository(session)
    group = await repo.get_by_id(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    payload = body.model_dump(exclude_unset=True)
    if not payload:
        raise HTTPException(status_code=400, detail="No fields to update")
    await repo.update_metadata(group, **payload)
    await log_admin_action(
        session, actor, "update_group",
        entity_type="group", entity_id=group.id,
        new_value={**payload, "source": "web"},
    )
    return await load_group_item(session, group)


@router.post("/{group_id}/approve")
async def approve_group(
    group_id: int,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_admin_actor),
):
    repo = GroupRepository(session)
    group = await repo.get_by_id(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if group.is_approved:
        raise HTTPException(status_code=400, detail="Group already approved")
    if group.is_frozen:
        raise HTTPException(status_code=400, detail="Unfreeze group before approval")
    await repo.approve(group, approved_by_id=actor.id)
    await log_admin_action(
        session, actor, "approve_group",
        entity_type="group", entity_id=group.id,
        new_value={"telegram_group_id": group.telegram_group_id, "source": "web"},
    )
    await tg.send_message(
        group.telegram_group_id,
        "✅ Группа одобрена!\n\n"
        "Сообщайте об ошибках командой:\n"
        "<code>/err номер_сип</code>\n"
        "Пример: <code>/err 100</code>",
    )
    return {"ok": True}


@router.post("/{group_id}/reject")
async def reject_group(
    group_id: int,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_admin_actor),
):
    repo = GroupRepository(session)
    group = await repo.get_by_id(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    telegram_id = group.telegram_group_id
    await repo.reject(group)
    await log_admin_action(
        session, actor, "reject_group",
        entity_type="group", entity_id=group_id,
        new_value={"telegram_group_id": telegram_id, "source": "web"},
    )
    await tg.send_message(telegram_id, "❌ Группа не была одобрена администратором.", parse_mode=None)
    await tg.leave_chat(telegram_id)
    return {"ok": True}


@router.post("/{group_id}/ban")
async def ban_group(
    group_id: int,
    body: BanBody,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_admin_actor),
):
    repo = GroupRepository(session)
    group = await repo.get_by_id(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    await repo.ban(group, body.reason)
    await log_admin_action(
        session, actor, "ban_group",
        entity_type="group", entity_id=group.id,
        new_value={"telegram_group_id": group.telegram_group_id, "reason": body.reason, "source": "web"},
    )
    await tg.send_message(group.telegram_group_id, f"🚫 Группа заблокирована. Причина: {body.reason}")
    await tg.leave_chat(group.telegram_group_id)
    return {"ok": True}


@router.post("/{group_id}/unban")
async def unban_group(
    group_id: int,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_admin_actor),
):
    repo = GroupRepository(session)
    group = await repo.get_by_id(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    await repo.unban(group)
    await log_admin_action(
        session, actor, "unban_group",
        entity_type="group", entity_id=group.id,
        new_value={"telegram_group_id": group.telegram_group_id, "source": "web"},
    )
    return {"ok": True}


@router.post("/{group_id}/owner")
async def set_group_owner(
    group_id: int,
    body: GroupOwnerBody,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_admin_actor),
):
    group_repo = GroupRepository(session)
    user_repo = UserRepository(session)
    group = await group_repo.get_by_id(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    owner = await user_repo.get_by_telegram_id(body.telegram_id)
    if not owner:
        raise HTTPException(status_code=404, detail="Owner user not found")
    old_owner = group.owner_user_id
    await group_repo.set_owner(group, owner.id)
    await log_admin_action(
        session, actor, "set_group_owner",
        entity_type="group", entity_id=group.id,
        old_value={"owner_user_id": old_owner},
        new_value={"owner_user_id": owner.id, "source": "web"},
    )
    return {"ok": True, "owner": user_brief(owner)}


@router.post("/{group_id}/freeze")
async def freeze_group(
    group_id: int,
    body: GroupFreezeBody,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_admin_actor),
):
    repo = GroupRepository(session)
    group = await repo.get_by_id(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if group.is_banned:
        raise HTTPException(status_code=400, detail="Cannot freeze banned group")
    if group.is_frozen:
        return {"ok": True, "noop": True}
    await repo.freeze(group, body.reason)
    await log_admin_action(
        session, actor, "freeze_group",
        entity_type="group", entity_id=group.id,
        new_value={"reason": body.reason, "source": "web"},
    )
    msg = "⏸ Колл-центр группы временно заморожен."
    if body.reason:
        msg += f"\nПричина: {body.reason}"
    msg += "\n\nСоздание заявок <code>/err</code> недоступно до разморозки."
    await tg.send_message(group.telegram_group_id, msg)
    return {"ok": True}


@router.post("/{group_id}/unfreeze")
async def unfreeze_group(
    group_id: int,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_admin_actor),
):
    repo = GroupRepository(session)
    group = await repo.get_by_id(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if not group.is_frozen:
        return {"ok": True, "noop": True}
    await repo.unfreeze(group)
    await log_admin_action(
        session, actor, "unfreeze_group",
        entity_type="group", entity_id=group.id,
        new_value={"source": "web"},
    )
    if group.is_approved:
        await tg.send_message(
            group.telegram_group_id,
            "▶️ Колл-центр группы снова активен.\n"
            "Сообщайте об ошибках: <code>/err номер_сип</code>",
        )
    return {"ok": True}


@router.post("/{group_id}/delete")
async def delete_group(
    group_id: int,
    session: AsyncSession = Depends(get_session),
    actor: User = Depends(get_admin_actor),
):
    repo = GroupRepository(session)
    group = await repo.get_by_id(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    telegram_id = group.telegram_group_id
    if not group.is_approved:
        await repo.reject(group)
    else:
        await repo.soft_delete(group)
        await tg.send_message(
            telegram_id,
            "🗑 Колл-центр группы отключён администратором.",
            parse_mode=None,
        )
        await tg.leave_chat(telegram_id)
    await log_admin_action(
        session, actor, "delete_group",
        entity_type="group", entity_id=group_id,
        new_value={"telegram_group_id": telegram_id, "source": "web"},
    )
    return {"ok": True}
