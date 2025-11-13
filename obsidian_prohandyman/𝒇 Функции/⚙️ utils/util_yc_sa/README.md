util_yc_sa

Утилиты для работы с сервисными аккаунтами Yandex Cloud.

loader.py

YcSaLoader(bootstrap_sdk=None)
Унифицированный загрузчик контекста сервисного аккаунта.
Источники: Lockbox (по secret_id или по folder_id+name), локальный JSON-файл.

from_lockbox_by_id(folder_id, sa_name, secret_id, key_field="key.json", version_id=None)
Загружает ключ из Lockbox по secret_id.
Возвращает SAContext с sdk и service_account.

from_lockbox_by_name(folder_id, sa_name, lockbox_folder_id, lockbox_secret_name, key_field="key.json", version_id=None)
Загружает ключ из Lockbox по имени секрета (без secret_id).
Возвращает SAContext с sdk и service_account.

from_local_file(folder_id, sa_name, key_file_path)
Загружает ключ из локального JSON-файла authorized key.
Возвращает SAContext с sdk и service_account.

make_ydb_credentials_from_sa_key_dict(sa_key)
Создает креденшелы для YDB из словаря ключа SA.
Использует временный файл для соответствия документации YDB.
Возвращает ydb.iam.ServiceAccountCredentials.

types.py

ServiceAccountObject
Dataclass с полями: id, name, folder_id.
Описание объект сервисного аккаунта.

SAContext
Dataclass с полями: sdk, service_account.
Контекст для вызовов YC API под целевым SA.
