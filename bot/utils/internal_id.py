import random
import string
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models.user import User


def _generate_id() -> str:
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(random.choices(chars, k=5))
    return f"CL-{suffix}"


async def generate_unique_internal_id(session: AsyncSession) -> str:
    for _ in range(10):
        candidate = _generate_id()
        result = await session.execute(
            select(User).where(User.internal_id == candidate)
        )
        if result.scalar_one_or_none() is None:
            return candidate
    raise RuntimeError("Не удалось сгенерировать уникальный internal_id")
