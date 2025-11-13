```python
class AuthError(Exception):
    """Ошибка аутентификации или прав доступа."""
    pass

class LogicError(Exception):
    """Ошибка в логике запроса (неверные параметры)."""
    pass

class PreconditionFailedError(Exception):
    """Ошибка, когда одно из предусловий для выполнения операции не выполнено."""
    pass
```