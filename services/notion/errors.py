"""Исключения клиента Notion."""


class NotionError(Exception):
    def __init__(self, message: str, *, status_code: int = 0, code: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


class NotionDisabledError(NotionError):
    def __init__(self, message: str = "Интеграция Notion отключена"):
        super().__init__(message, status_code=503, code="notion_disabled")


class NotionNotConfiguredError(NotionError):
    def __init__(self, message: str = "NOTION_API_TOKEN не задан"):
        super().__init__(message, status_code=503, code="notion_not_configured")
