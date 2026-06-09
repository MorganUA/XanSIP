from aiogram.fsm.state import State, StatesGroup


class TicketFSM(StatesGroup):
    selecting_sip = State()        # Пользователь выбирает SIP
    selecting_error_type = State() # Пользователь выбирает тип ошибки
    entering_description = State() # Ввод описания (если "Другое")
    confirming = State()           # Подтверждение перед отправкой
