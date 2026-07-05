from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.app_setting import AppSetting


class AppSettingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, key: str) -> AppSetting | None:
        result = await self.session.execute(
            select(AppSetting).where(AppSetting.key == key)
        )
        return result.scalar_one_or_none()

    async def get_value(self, key: str) -> dict | None:
        row = await self.get(key)
        return row.value if row else None

    async def set_value(self, key: str, value: dict, description: str | None = None) -> AppSetting:
        row = await self.get(key)
        if row:
            row.value = value
            if description is not None:
                row.description = description
        else:
            row = AppSetting(key=key, value=value, description=description)
            self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def list_all(self) -> list[AppSetting]:
        result = await self.session.execute(select(AppSetting).order_by(AppSetting.key))
        return list(result.scalars().all())
