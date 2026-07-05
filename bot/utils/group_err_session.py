import json
from dataclasses import asdict, dataclass

from redis.asyncio import Redis

SESSION_TTL = 300  # 5 minutes


@dataclass
class GroupErrSession:
    sip_number: str
    group_db_id: int
    sip_id: int
    owner_user_id: int


def _key(chat_id: int, user_id: int) -> str:
    return f"group_err:{chat_id}:{user_id}"


async def save_session(redis: Redis, chat_id: int, user_id: int, session: GroupErrSession) -> None:
    await redis.set(_key(chat_id, user_id), json.dumps(asdict(session)), ex=SESSION_TTL)


async def load_session(redis: Redis, chat_id: int, user_id: int) -> GroupErrSession | None:
    raw = await redis.get(_key(chat_id, user_id))
    if not raw:
        return None
    data = json.loads(raw)
    return GroupErrSession(**data)


async def clear_session(redis: Redis, chat_id: int, user_id: int) -> None:
    await redis.delete(_key(chat_id, user_id))
