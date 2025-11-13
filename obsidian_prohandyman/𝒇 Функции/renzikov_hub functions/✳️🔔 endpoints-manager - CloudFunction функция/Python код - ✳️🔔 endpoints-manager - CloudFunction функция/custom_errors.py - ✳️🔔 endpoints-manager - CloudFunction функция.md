# custom_errors.py
```python
from utils import Forbidden, BadRequest, NotFound

# Алиасы для единообразия с общими утилитами ошибок
AuthError = Forbidden
LogicError = BadRequest
NotFoundError = NotFound
```