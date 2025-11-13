util_ydb

Управление YDB драйверами и пулами сессий с кешированием.

driver.py

get_driver(endpoint, database, sa_key_file=None, sa_key_var=None, wait_timeout_sec=5.0, credentials=None)
Создает и кеширует YDB драйвер для endpoint/database пары.
Использует Service Account из файла (sa_key_file или переменная окружения).
Если передан credentials - драйвер не кешируется.
Возвращает ydb.Driver.

get_session_pool(endpoint, database, sa_key_file=None, sa_key_var=None, wait_timeout_sec=5.0, credentials=None)
Создает и кеширует SessionPool привязанный к драйверу.
Параметры аналогичны get_driver.
Возвращает ydb.SessionPool.

get_driver_from_env(endpoint_var="YDB_ENDPOINT", database_var="YDB_DATABASE", sa_key_var="SA_KEY_FILE", wait_timeout_sec=5.0)
Создает драйвер используя переменные окружения для endpoint и database.
Возвращает ydb.Driver.

get_session_pool_from_env(endpoint_var="YDB_ENDPOINT", database_var="YDB_DATABASE", sa_key_var="SA_KEY_FILE", wait_timeout_sec=5.0)
Создает пул сессий используя переменные окружения.
Возвращает ydb.SessionPool.

Кеширование thread-safe. Один драйвер/пул на уникальную комбинацию endpoint+database+sa_key.
