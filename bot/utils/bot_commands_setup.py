import logging

from aiogram.types import BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats, MenuButtonWebApp, WebAppInfo

from bot.utils.webapp import get_mini_app_url

logger = logging.getLogger(__name__)


async def register_bot_commands(bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Главное меню"),
            BotCommand(command="help", description="Справка"),
            BotCommand(command="err", description="Заявка: /err SIP описание"),
            BotCommand(command="tickets", description="Мои заявки"),
            BotCommand(command="mysip", description="SIP-номера"),
            BotCommand(command="balance", description="Баланс USDT"),
            BotCommand(command="deposit", description="Пополнение USDT"),
            BotCommand(command="profile", description="Профиль"),
            BotCommand(command="myid", description="Мой ID"),
            BotCommand(command="guides", description="Руководства по эксплуатации"),
            BotCommand(command="rules", description="Правила"),
            BotCommand(command="admin", description="Поддержка"),
        ],
        scope=BotCommandScopeAllPrivateChats(),
    )
    await bot.set_my_commands(
        [
            BotCommand(command="err", description="Сообщить об ошибке (SIP)"),
            BotCommand(command="status", description="Активные заявки группы"),
            BotCommand(command="sips", description="SIP-номера владельца"),
            BotCommand(command="help", description="Справка для группы"),
        ],
        scope=BotCommandScopeAllGroupChats(),
    )
    mini_url = get_mini_app_url()
    if not mini_url:
        return
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="SIP CRM", web_app=WebAppInfo(url=mini_url)),
        )
    except Exception:
        logger.exception("Не удалось установить MenuButton Web App (%s)", mini_url)
