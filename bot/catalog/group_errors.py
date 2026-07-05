from dataclasses import dataclass

from db.models.ticket import ErrorType


@dataclass(frozen=True)
class GroupErrorPreset:
    id: str
    button: str
    label: str
    error_type: ErrorType


# Быстрый выбор (3 кнопки на первом экране)
MAIN_PRESET_IDS = ("gd_fraud", "gd_balance", "gd_nodial")

# Подменю «Ещё проблемы» (6 кнопок)
SUBMENU_PRESET_IDS = (
    "gd_noreg",
    "gd_busy",
    "gd_sim",
    "gd_timeout",
    "gd_noaudio",
    "gd_blocked",
)

GROUP_ERROR_PRESETS: dict[str, GroupErrorPreset] = {
    "gd_fraud": GroupErrorPreset(
        "gd_fraud", "🚫 Фрод", "Фрод", ErrorType.other,
    ),
    "gd_balance": GroupErrorPreset(
        "gd_balance", "💳 Нет баланса", "Нет баланса", ErrorType.no_balance,
    ),
    "gd_nodial": GroupErrorPreset(
        "gd_nodial", "📞 Недозвон", "Недозвон", ErrorType.no_calls,
    ),
    "gd_noreg": GroupErrorPreset(
        "gd_noreg", "❌ Нет регистрации", "Нет регистрации", ErrorType.no_registration,
    ),
    "gd_busy": GroupErrorPreset(
        "gd_busy", "📵 Busy Here", "Busy Here", ErrorType.busy_here,
    ),
    "gd_sim": GroupErrorPreset(
        "gd_sim", "📱 SIM", "Проблема с SIM", ErrorType.sim_problem,
    ),
    "gd_timeout": GroupErrorPreset(
        "gd_timeout", "⏱ 408 Timeout", "408 Timeout", ErrorType.no_registration,
    ),
    "gd_noaudio": GroupErrorPreset(
        "gd_noaudio", "🔇 Нет звука", "Нет звука", ErrorType.no_calls,
    ),
    "gd_blocked": GroupErrorPreset(
        "gd_blocked", "🚷 Заблокирован", "Номер заблокирован", ErrorType.other,
    ),
}


def get_group_preset(preset_id: str) -> GroupErrorPreset | None:
    return GROUP_ERROR_PRESETS.get(preset_id)
