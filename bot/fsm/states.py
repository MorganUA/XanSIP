from aiogram.fsm.state import State, StatesGroup


class FinanceFSM(StatesGroup):
    entering_amount = State()
    entering_tx_hash = State()


class TicketFSM(StatesGroup):
    selecting_sip = State()
    selecting_error_type = State()       # выбор категории ошибки
    selecting_error_preset = State()   # выбор из справочника
    entering_description = State()
    confirming = State()
