class UrlError(Exception):
    """Http запрос перенаправлен или не доступен для пользователя."""


class StatusError(Exception):
    """Отсутсвует новый статус проверки проекта."""
