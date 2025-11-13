
```python
class AuthError(Exception):
    """Ошибка авторизации или недостаточных прав."""
    pass

class LogicError(Exception):
    """Логическая ошибка в запросе или данных."""
    pass

class NotFoundError(Exception):
    """Запрашиваемый ресурс не найден."""
    pass
```
