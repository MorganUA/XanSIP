from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.catalog.errors import (
    CATEGORY_LABELS,
    ErrorCategory,
    PRESETS_PER_PAGE,
    get_presets_for_category,
)
from db.models.ticket import ErrorType

TEST_PREFIX = "testerr"
TICKET_PREFIX = "error"


def _cat_callback(prefix: str, sip_id: int, category: ErrorCategory) -> str:
    if prefix == TEST_PREFIX:
        return f"{prefix}:cat:{category.value}"
    return f"{prefix}:cat:{sip_id}:{category.value}"


def _preset_callback(prefix: str, sip_id: int, preset_id: str) -> str:
    if prefix == TEST_PREFIX:
        return f"{prefix}:preset:{preset_id}"
    return f"{prefix}:preset:{sip_id}:{preset_id}"


def _page_callback(prefix: str, sip_id: int, category: ErrorCategory, page: int) -> str:
    if prefix == TEST_PREFIX:
        return f"{prefix}:page:{category.value}:{page}"
    return f"{prefix}:page:{sip_id}:{category.value}:{page}"


def _back_callback(prefix: str, sip_id: int) -> str:
    if prefix == TEST_PREFIX:
        return f"{prefix}:back"
    return f"{prefix}:back:{sip_id}"


def get_error_category_keyboard(
    sip_id: int = 0,
    *,
    prefix: str = TICKET_PREFIX,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for category in ErrorCategory:
        builder.button(
            text=CATEGORY_LABELS[category],
            callback_data=_cat_callback(prefix, sip_id, category),
        )

    if prefix == TICKET_PREFIX:
        builder.button(
            text="💬 Своя ошибка",
            callback_data=f"{prefix}:type:{sip_id}:{ErrorType.other.value}",
        )
        builder.button(text="❌ Отмена", callback_data="ticket:cancel")
    else:
        builder.button(text="❌ Закрыть", callback_data=f"{prefix}:close")

    builder.adjust(1)
    return builder.as_markup()


def get_error_presets_keyboard(
    category: ErrorCategory,
    page: int = 0,
    *,
    sip_id: int = 0,
    prefix: str = TICKET_PREFIX,
) -> InlineKeyboardMarkup:
    presets = get_presets_for_category(category)
    total_pages = max(1, (len(presets) + PRESETS_PER_PAGE - 1) // PRESETS_PER_PAGE)
    page = max(0, min(page, total_pages - 1))
    start = page * PRESETS_PER_PAGE
    chunk = presets[start:start + PRESETS_PER_PAGE]

    builder = InlineKeyboardBuilder()
    for preset in chunk:
        builder.button(
            text=preset.button,
            callback_data=_preset_callback(prefix, sip_id, preset.id),
        )
    builder.adjust(2)

    nav = []
    if page > 0:
        nav.append(("◀️", _page_callback(prefix, sip_id, category, page - 1)))
    if page < total_pages - 1:
        nav.append(("▶️", _page_callback(prefix, sip_id, category, page + 1)))
    for text, data in nav:
        builder.button(text=text, callback_data=data)

    builder.button(text="◀️ К категориям", callback_data=_back_callback(prefix, sip_id))
    if prefix == TICKET_PREFIX:
        builder.button(text="❌ Отмена", callback_data="ticket:cancel")
    else:
        builder.button(text="❌ Закрыть", callback_data=f"{prefix}:close")

    if nav:
        builder.adjust(2, len(nav), 2)
    else:
        builder.adjust(2, 2)
    return builder.as_markup()
