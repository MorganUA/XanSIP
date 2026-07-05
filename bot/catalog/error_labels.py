from db.models.ticket import ErrorType

ERROR_TYPE_LABELS = {
    ErrorType.busy_here: "📵 Busy Here",
    ErrorType.no_registration: "❌ Нет регистрации",
    ErrorType.no_calls: "📞 Не проходят звонки",
    ErrorType.no_balance: "💳 Кончился баланс",
    ErrorType.sim_problem: "📱 Проблема с SIM",
    ErrorType.other: "💬 Другое",
}
