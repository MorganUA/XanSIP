from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession
from db.models.user import User
from db.models.sip_account import SipStatus
from db.repositories.sip_repo import SipRepository

router = Router()

STATUS_ICONS = {
    SipStatus.active: "🟢 Активен",
    SipStatus.frozen: "🟡 Заморожен",
    SipStatus.disabled: "🔴 Отключён",
}


@router.message(F.text == "📞 Мои SIP")
@router.message(Command("mysip"))
async def show_my_sip(message: Message, user: User, session: AsyncSession):
    repo = SipRepository(session)
    sips = await repo.get_by_user_id(user.id)

    if not sips:
        await message.answer(
            "📞 У вас пока нет подключённых SIP-номеров.\n\n"
            "Обратитесь к администратору для подключения."
        )
        return

    lines = ["📞 <b>Ваши SIP-номера:</b>\n"]
    for sip in sips:
        status = STATUS_ICONS.get(sip.status, "⚪ Неизвестно")
        line = f"• <code>{sip.sip_number}</code> — {status}"
        if sip.description:
            line += f"\n  📝 {sip.description}"
        if sip.expires_at:
            line += f"\n  📅 До: {sip.expires_at.strftime('%d.%m.%Y')}"
        lines.append(line)

    await message.answer("\n".join(lines), parse_mode="HTML")
