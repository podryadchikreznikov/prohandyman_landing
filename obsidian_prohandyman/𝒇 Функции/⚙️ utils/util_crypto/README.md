util_crypto

Криптографические операции: JWT токены и хеширование паролей.

jwt_tokens.py

issue_jwt(subject, secret, claims=None, expires_in_sec=None, algorithm="HS256")
Создает JWT токен. По умолчанию бессрочный (без exp). Для TTL передать expires_in_sec.
Возвращает строку токена.

verify_jwt(token, secret, verify_exp=False, algorithms=("HS256",), leeway_sec=30)
Проверяет JWT токен. По умолчанию НЕ проверяет exp. Для проверки TTL: verify_exp=True.
Возвращает dict с payload или выбрасывает исключение.

password.py

hash_password(password, format="legacy_bcrypt", iterations=200000)
Хеширует пароль. Форматы:
- legacy_bcrypt: чистый bcrypt без префикса (совместимость с БД)
- bcrypt_tagged: bcrypt$ + хеш
- pbkdf2: pbkdf2_sha256$iterations$salt$hex
Требует библиотеку bcrypt для bcrypt форматов.

verify_password(password, stored)
Проверяет пароль против хеша. Автоматически определяет формат (bcrypt$/pbkdf2_sha256$/legacy).
Возвращает bool.
