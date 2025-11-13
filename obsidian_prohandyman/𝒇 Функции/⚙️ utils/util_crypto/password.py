import hmac, hashlib, secrets
from typing import Literal

try:
    import bcrypt
    _HAS_BCRYPT = True
except Exception:
    _HAS_BCRYPT = False

def hash_password(password: str, *, format: Literal["legacy_bcrypt","bcrypt_tagged","pbkdf2"]="legacy_bcrypt", iterations: int = 200_000) -> str:
    """
    format:
      - legacy_bcrypt (по умолчанию): возвращает ЧИСТЫЙ bcrypt-хэш без префикса — ИДЕНТИЧНО твоим текущим записям БД.
      - bcrypt_tagged: вернёт 'bcrypt$<hash>' — удобно при миграциях/смешанных форматах.
      - pbkdf2: 'pbkdf2_sha256$<iterations>$<salt>$<hex>'.
    """
    if format in ("legacy_bcrypt", "bcrypt_tagged"):
        if not _HAS_BCRYPT: raise RuntimeError("bcrypt not installed; use pbkdf2")
        h = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        return h if format == "legacy_bcrypt" else f"bcrypt${h}"
    elif format == "pbkdf2":
        salt = secrets.token_hex(16)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations)
        return f"pbkdf2_sha256${iterations}${salt}${dk.hex()}"
    else:
        raise ValueError("Unknown format")

def verify_password(password: str, stored: str) -> bool:
    # поддержка трёх кейсов: 'bcrypt$…', чистый bcrypt, 'pbkdf2_sha256$…'
    if stored.startswith("bcrypt$"):
        if not _HAS_BCRYPT: return False
        return bcrypt.checkpw(password.encode("utf-8"), stored.split("$",1)[1].encode("utf-8"))
    if stored.startswith("pbkdf2_sha256$"):
        try:
            _, iters, salt, hexd = stored.split("$", 3)
            dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iters))
            return hmac.compare_digest(dk.hex(), hexd)
        except Exception:
            return False
    # legacy — чистый bcrypt без префикса
    if _HAS_BCRYPT:
        try: return bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8"))
        except Exception: return False
    return False