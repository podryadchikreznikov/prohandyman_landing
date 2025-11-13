
```python
from utils import BadRequest, Forbidden, NotFound

# Backwards-compatible aliases to shared util errors
AuthError = Forbidden
LogicError = BadRequest
NotFoundError = NotFound
```