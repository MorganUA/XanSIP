from dataclasses import dataclass
from enum import Enum

from db.models.ticket import ErrorType


class ErrorCategory(str, Enum):
    microsip = "microsip"
    operator = "operator"
    quick = "quick"


CATEGORY_LABELS = {
    ErrorCategory.microsip: "📱 MicroSIP",
    ErrorCategory.operator: "📡 Автоответчик оператора",
    ErrorCategory.quick: "⚡ Частые проблемы",
}


@dataclass(frozen=True)
class ErrorPreset:
    id: str
    category: ErrorCategory
    button: str
    title: str
    description: str
    error_type: ErrorType


ERROR_PRESETS: dict[str, ErrorPreset] = {
    # ─── MicroSIP / SIP ───────────────────────────────────────────
    "ms408": ErrorPreset(
        "ms408", ErrorCategory.microsip, "408 Timeout",
        "408 Request Timeout",
        "MicroSIP: 408 Request Timeout — нет ответа от сервера, проверьте сеть и SIP-сервер.",
        ErrorType.no_registration,
    ),
    "ms486": ErrorPreset(
        "ms486", ErrorCategory.microsip, "486 Busy Here",
        "486 Busy Here",
        "MicroSIP: 486 Busy Here — линия занята или отклонён вызов.",
        ErrorType.busy_here,
    ),
    "ms404": ErrorPreset(
        "ms404", ErrorCategory.microsip, "404 Not Found",
        "404 Not Found",
        "MicroSIP: 404 Not Found — номер или маршрут не найден на стороне оператора.",
        ErrorType.no_calls,
    ),
    "ms403": ErrorPreset(
        "ms403", ErrorCategory.microsip, "403 Forbidden",
        "403 Forbidden",
        "MicroSIP: 403 Forbidden — доступ запрещён, проверьте авторизацию и ACL.",
        ErrorType.no_registration,
    ),
    "ms503": ErrorPreset(
        "ms503", ErrorCategory.microsip, "503 Unavailable",
        "503 Service Unavailable",
        "MicroSIP: 503 Service Unavailable — SIP-сервис временно недоступен.",
        ErrorType.no_registration,
    ),
    "ms401": ErrorPreset(
        "ms401", ErrorCategory.microsip, "401 Unauthorized",
        "401 Unauthorized",
        "MicroSIP: 401 Unauthorized — неверный логин/пароль SIP или истёк пароль.",
        ErrorType.no_registration,
    ),
    "ms603": ErrorPreset(
        "ms603", ErrorCategory.microsip, "603 Decline",
        "603 Decline",
        "MicroSIP: 603 Decline — вызов отклонён сервером или абонентом.",
        ErrorType.busy_here,
    ),
    "ms_noreg": ErrorPreset(
        "ms_noreg", ErrorCategory.microsip, "Нет регистрации",
        "Нет регистрации (Offline)",
        "MicroSIP: нет регистрации на SIP-сервере, статус Offline / Not Registered.",
        ErrorType.no_registration,
    ),
    "ms_oneway": ErrorPreset(
        "ms_oneway", ErrorCategory.microsip, "Односторонняя связь",
        "Односторонняя аудиосвязь",
        "MicroSIP: слышно только в одну сторону (RTP/NAT/firewall).",
        ErrorType.no_calls,
    ),
    "ms_noaudio": ErrorPreset(
        "ms_noaudio", ErrorCategory.microsip, "Нет аудио",
        "Нет аудио",
        "MicroSIP: вызов проходит, но нет звука в обе стороны.",
        ErrorType.no_calls,
    ),
    "ms_codec": ErrorPreset(
        "ms_codec", ErrorCategory.microsip, "Кодеки",
        "Проблема кодеков",
        "MicroSIP: ошибка кодеков (488 Not Acceptable / несовместимость codec).",
        ErrorType.no_calls,
    ),
    "ms_dns": ErrorPreset(
        "ms_dns", ErrorCategory.microsip, "DNS / хост",
        "DNS / SIP-хост",
        "MicroSIP: не резолвится SIP-домен или неверный proxy/registrar.",
        ErrorType.no_registration,
    ),
    # ─── Автоответчики операторов ─────────────────────────────────
    "op_unavail": ErrorPreset(
        "op_unavail", ErrorCategory.operator, "Абонент недоступен",
        "Абонент недоступен",
        "Автоответчик: «Абонент недоступен» / «The subscriber is unavailable».",
        ErrorType.no_calls,
    ),
    "op_not_serviced": ErrorPreset(
        "op_not_serviced", ErrorCategory.operator, "Не обслуживается",
        "Номер не обслуживается",
        "Автоответчик: «Номер не обслуживается» / «Number not in service».",
        ErrorType.no_calls,
    ),
    "op_wrong": ErrorPreset(
        "op_wrong", ErrorCategory.operator, "Неверный номер",
        "Неверно набран номер",
        "Автоответчик: «Неверно набран номер» / «Invalid number».",
        ErrorType.no_calls,
    ),
    "op_blocked": ErrorPreset(
        "op_blocked", ErrorCategory.operator, "Заблокирован",
        "Номер временно заблокирован",
        "Автоответчик: «Номер временно заблокирован» / «Temporarily blocked».",
        ErrorType.sim_problem,
    ),
    "op_no_pay": ErrorPreset(
        "op_no_pay", ErrorCategory.operator, "Отключена оплата",
        "Отключена оплата услуг",
        "Автоответчик: «У абонента отключена оплата услуг» / «Services suspended».",
        ErrorType.no_balance,
    ),
    "op_busy": ErrorPreset(
        "op_busy", ErrorCategory.operator, "Абонент занят",
        "Абонент занят",
        "Автоответчик: «Абонент занят» / «Subscriber busy» / гудки занято.",
        ErrorType.busy_here,
    ),
    "op_no_answer": ErrorPreset(
        "op_no_answer", ErrorCategory.operator, "Не отвечает",
        "Номер не отвечает",
        "Автоответчик: «Номер не отвечает» — долгие гудки без ответа.",
        ErrorType.no_calls,
    ),
    "op_balance": ErrorPreset(
        "op_balance", ErrorCategory.operator, "Недостаточно средств",
        "Недостаточно средств",
        "Автоответчик: «На вашем счету недостаточно средств» / «Insufficient balance».",
        ErrorType.no_balance,
    ),
    "op_roaming": ErrorPreset(
        "op_roaming", ErrorCategory.operator, "Роуминг",
        "Услуга недоступна в роуминге",
        "Автоответчик: «Услуга недоступна в роуминге» / «Not available while roaming».",
        ErrorType.no_calls,
    ),
    "op_voicemail": ErrorPreset(
        "op_voicemail", ErrorCategory.operator, "Голосовая почта",
        "Переадресация на голосовую почту",
        "Автоответчик: перевод на голосовую почту / автоответчик абонента.",
        ErrorType.no_calls,
    ),
    "op_network": ErrorPreset(
        "op_network", ErrorCategory.operator, "Сеть недоступна",
        "Сеть оператора недоступна",
        "Автоответчик: «Сеть временно недоступна» / «Network unavailable».",
        ErrorType.no_calls,
    ),
    # ─── Частые (быстрый выбор) ───────────────────────────────────
    "qk_balance": ErrorPreset(
        "qk_balance", ErrorCategory.quick, "💳 Баланс",
        "Кончился баланс",
        "Кончился баланс на SIP/линии.",
        ErrorType.no_balance,
    ),
    "qk_noreg": ErrorPreset(
        "qk_noreg", ErrorCategory.quick, "❌ Нет регистрации",
        "Нет регистрации",
        "SIP не регистрируется на сервере.",
        ErrorType.no_registration,
    ),
    "qk_nocalls": ErrorPreset(
        "qk_nocalls", ErrorCategory.quick, "📞 Не проходят",
        "Не проходят звонки",
        "Звонки не проходят или обрываются.",
        ErrorType.no_calls,
    ),
    "qk_busy": ErrorPreset(
        "qk_busy", ErrorCategory.quick, "📵 Busy Here",
        "Busy Here",
        "Busy Here / линия занята.",
        ErrorType.busy_here,
    ),
    "qk_sim": ErrorPreset(
        "qk_sim", ErrorCategory.quick, "📱 SIM",
        "Проблема с SIM",
        "Проблема с SIM-картой или слотом.",
        ErrorType.sim_problem,
    ),
}

PRESETS_BY_CATEGORY: dict[ErrorCategory, list[str]] = {
    ErrorCategory.microsip: [
        "ms408", "ms486", "ms404", "ms403", "ms503", "ms401", "ms603",
        "ms_noreg", "ms_oneway", "ms_noaudio", "ms_codec", "ms_dns",
    ],
    ErrorCategory.operator: [
        "op_unavail", "op_not_serviced", "op_wrong", "op_blocked", "op_no_pay",
        "op_busy", "op_no_answer", "op_balance", "op_roaming", "op_voicemail", "op_network",
    ],
    ErrorCategory.quick: [
        "qk_balance", "qk_noreg", "qk_nocalls", "qk_busy", "qk_sim",
    ],
}

PRESETS_PER_PAGE = 8


def get_preset(preset_id: str) -> ErrorPreset | None:
    return ERROR_PRESETS.get(preset_id)


def get_presets_for_category(category: ErrorCategory) -> list[ErrorPreset]:
    return [
        ERROR_PRESETS[pid]
        for pid in PRESETS_BY_CATEGORY.get(category, [])
        if pid in ERROR_PRESETS
    ]


def get_preset_label(preset_id: str | None, description: str) -> str:
    if preset_id:
        preset = get_preset(preset_id)
        if preset:
            return f"{CATEGORY_LABELS[preset.category]} → {preset.title}"
    return description
