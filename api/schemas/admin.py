from pydantic import BaseModel, Field

from db.models.ticket import TicketStatus
from db.models.user import UserRole


class BanBody(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class RoleBody(BaseModel):
    role: UserRole


class AddSipBody(BaseModel):
    telegram_id: int
    sip_number: str = Field(min_length=1, max_length=50)
    description: str | None = None
    auth_username: str | None = Field(default=None, max_length=120)
    auth_password: str | None = Field(default=None, max_length=128)


class SipCredentialsBody(BaseModel):
    auth_username: str | None = Field(default=None, max_length=120)
    auth_password: str | None = Field(default=None, min_length=1, max_length=128)


class SoftphoneTrunkBody(BaseModel):
    enabled: bool = False
    wss_url: str = ""
    sip_domain: str = ""
    display_name: str = "SIP CRM"
    stun_servers: list[str] = Field(default_factory=list)
    turn_url: str = ""
    turn_username: str = ""
    turn_credential: str = ""
    dial_prefix: str = ""
    outbound_proxy: str = ""
    session_ttl_seconds: int = Field(default=300, ge=60, le=900)


class TicketStatusBody(BaseModel):
    status: TicketStatus
    comment: str | None = None


class GroupOwnerBody(BaseModel):
    telegram_id: int


class GroupCreateBody(BaseModel):
    telegram_group_id: int
    group_name: str | None = Field(default=None, max_length=255)
    call_center_label: str | None = Field(default=None, max_length=255)
    tariff: str | None = Field(default=None, max_length=120)
    tariff_notes: str | None = None
    work_conditions: str | None = None
    participants_info: str | None = None
    contact_info: str | None = None
    notes: str | None = None
    owner_telegram_id: int | None = None


class GroupUpdateBody(BaseModel):
    group_name: str | None = Field(default=None, max_length=255)
    call_center_label: str | None = Field(default=None, max_length=255)
    tariff: str | None = Field(default=None, max_length=120)
    tariff_notes: str | None = None
    work_conditions: str | None = None
    participants_info: str | None = None
    contact_info: str | None = None
    notes: str | None = None


class GroupFreezeBody(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class LoginBody(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)
    captcha: str = Field(min_length=1, max_length=8)


class CreateTicketBody(BaseModel):
    sip_number: str = Field(min_length=1, max_length=50)
    error_preset_id: str = Field(min_length=1, max_length=50)
    initiator_telegram_id: int
    group_chat_id: int


class NotificationSettingsBody(BaseModel):
    support_chat_ids: list[int] = Field(default_factory=list)
    admin_chat_ids: list[int] = Field(default_factory=list)
    events: dict[str, dict[str, bool]] = Field(default_factory=dict)
