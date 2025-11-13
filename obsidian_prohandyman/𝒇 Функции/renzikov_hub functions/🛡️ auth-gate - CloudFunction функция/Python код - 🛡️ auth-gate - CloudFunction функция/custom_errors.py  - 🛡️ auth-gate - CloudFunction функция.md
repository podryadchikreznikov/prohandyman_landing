```python
# Используем стандартизированные исключения из util_errors
from utils.util_errors.exceptions import Unauthorized, Forbidden

# Алиасы для обратной совместимости (если где-то используется AuthError)
AuthError = Unauthorized
```