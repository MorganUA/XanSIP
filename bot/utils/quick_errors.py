"""Shared quick-error presets (same as group /err main screen)."""

from bot.catalog.group_errors import GROUP_ERROR_PRESETS, MAIN_PRESET_IDS, get_group_preset

OTHER_ERROR_BUTTON = "📋 Другая ошибка"


def quick_error_button_texts() -> tuple[str, ...]:
    return tuple(GROUP_ERROR_PRESETS[pid].button for pid in MAIN_PRESET_IDS)


def preset_id_from_button(text: str) -> str | None:
    for preset_id in MAIN_PRESET_IDS:
        if GROUP_ERROR_PRESETS[preset_id].button == text:
            return preset_id
    return None


def preset_confirm_label(preset_id: str) -> str:
    preset = get_group_preset(preset_id)
    return preset.label if preset else preset_id
