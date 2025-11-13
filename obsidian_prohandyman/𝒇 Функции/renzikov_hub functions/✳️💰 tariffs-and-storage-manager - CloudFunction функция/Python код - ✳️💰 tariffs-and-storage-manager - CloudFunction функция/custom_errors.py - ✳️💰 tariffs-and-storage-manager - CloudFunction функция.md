```python
from utils import Forbidden, BadRequest, NotFound

# Алиасы для единообразия с утилитами ошибок
AuthError = Forbidden
LogicError = BadRequest
NotFoundError = NotFound

class QuotaExceededError(Exception): pass
```