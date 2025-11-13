```python
import json
import os
import ydb
from custom_errors import NotFoundError
import password_manager_email  # <<< ИЗМЕНЕНИЕ: Импортируем локальный модуль
from utils import JsonLogger, ok

def handle_request_reset(session, email: str = None, phone_number: str = None):
    """
    Находит пользователя по email или phone_number, извлекает хеш его пароля и отправляет на почту.
    """
    logger = JsonLogger()
    tx = session.transaction(ydb.SerializableReadWrite())

    # 1. Ищем активного пользователя по email или phone
    if email and phone_number:
        query_text = f"""
            PRAGMA TablePathPrefix('{os.environ['YDB_DATABASE']}');
            DECLARE $email AS Utf8; DECLARE $phone AS Utf8;
            SELECT password_hash, email, phone_number
            FROM users WHERE (email = $email OR phone_number = $phone) AND is_active = true LIMIT 1;
        """
        query_params = {'$email': email, '$phone': phone_number}
    elif email:
        query_text = f"""
            PRAGMA TablePathPrefix('{os.environ['YDB_DATABASE']}');
            DECLARE $email AS Utf8;
            SELECT password_hash, email, phone_number FROM users WHERE email = $email AND is_active = true;
        """
        query_params = {'$email': email}
    else:  # only phone
        query_text = f"""
            PRAGMA TablePathPrefix('{os.environ['YDB_DATABASE']}');
            DECLARE $phone AS Utf8;
            SELECT password_hash, email, phone_number FROM users WHERE phone_number = $phone AND is_active = true;
        """
        query_params = {'$phone': phone_number}
    
    result = tx.execute(session.prepare(query_text), query_params)

    if not result[0].rows:
        tx.rollback()
        raise NotFoundError("User with this email not found or is not active.")

    row = result[0].rows[0]
    current_password_hash = row.password_hash
    user_email = getattr(row, "email", None)
    tx.commit() # Завершаем транзакцию с БД перед отправкой email

    # 2. Отправляем email с хешем через локальный модуль (только если есть email)
    if user_email:
        email_sent = password_manager_email.send_password_reset_hash(
            recipient_email=user_email,
            password_hash=current_password_hash
        )
    else:
        # Если у пользователя нет email, нельзя отправить письмо
        logger.warn("password_manager.no_email", phone=phone_number)
        return ok({"message": "User found but has no email address for password reset."})

    if not email_sent:
        logger.error("password_manager.mail_failed", email=email)
        # Это внутренняя ошибка сервера, а не ошибка клиента
        raise Exception("Failed to send email.")

    logger.info("password_manager.mail_sent", email=user_email)
    return ok({"message": "Password reset instructions have been sent to your email."})
```