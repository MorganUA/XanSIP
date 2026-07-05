from bot.config import settings
from db.models.user import User, UserRole


def is_test_mode_enabled() -> bool:
    return settings.test_mode


def can_use_error_test_menu(user: User) -> bool:
    if not settings.test_mode:
        return False
    return user.role in (UserRole.admin, UserRole.superadmin, UserRole.support)
