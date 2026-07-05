"""Настройки финансовой системы (app_settings key: finance)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from db.repositories.app_setting_repo import AppSettingRepository

FINANCE_KEY = "finance"

DEFAULTS = {
    "min_deposit_usdt": 10,
    "max_deposit_usdt": 50000,
    "deposit_ttl_hours": 24,
    "instruction_text": (
        "Переведите <b>точную сумму</b> USDT на указанный адрес.\n"
        "Сеть должна совпадать. После оплаты нажмите «Я оплатил»."
    ),
    "currency_label": "USDT",
}


async def get_finance_config(session: AsyncSession) -> dict:
    repo = AppSettingRepository(session)
    stored = await repo.get_value(FINANCE_KEY)
    cfg = dict(DEFAULTS)
    if stored:
        cfg.update(stored)
    return cfg


async def save_finance_config(session: AsyncSession, data: dict) -> dict:
    repo = AppSettingRepository(session)
    cfg = await get_finance_config(session)
    cfg.update(data)
    await repo.set_value(FINANCE_KEY, cfg, description="Finance system settings")
    return cfg
