import datetime as dt
from typing import Any, Dict, Optional, Tuple
import jwt

def issue_jwt(subject: str, *, secret: str, claims: Optional[Dict[str, Any]] = None, expires_in_sec: Optional[int] = None, algorithm: str = "HS256") -> str:
    """
    По умолчанию НЕ выставляет exp (совместимо с 'бессрочными' токенами).
    Чтобы включить TTL: передай expires_in_sec (в секундах).
    """
    now = dt.datetime.now(dt.timezone.utc)
    payload = {"sub": subject, "iat": int(now.timestamp())}
    if expires_in_sec is not None:
        payload["exp"] = int((now + dt.timedelta(seconds=expires_in_sec)).timestamp())
    if claims: payload.update(claims)
    return jwt.encode(payload, secret, algorithm=algorithm)

def verify_jwt(token: str, *, secret: str, verify_exp: bool = False, algorithms: Tuple[str, ...] = ("HS256",), leeway_sec: int = 30) -> Dict[str, Any]:
    """
    По умолчанию НЕ проверяет exp (совместимо с 'бессрочными').
    Включить проверку: verify_exp=True.
    """
    return jwt.decode(token, secret, algorithms=list(algorithms), options={"verify_exp": verify_exp}, leeway=leeway_sec)