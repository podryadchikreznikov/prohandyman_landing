from __future__ import annotations
import json
import tempfile
from pathlib import Path
from typing import Optional, Dict

from yandexcloud import SDK

# IAM: сервис-аккаунты
from yandex.cloud.iam.v1.service_account_service_pb2 import ListServiceAccountsRequest
from yandex.cloud.iam.v1.service_account_service_pb2_grpc import ServiceAccountServiceStub

# Lockbox: содержимое секрета
from yandex.cloud.lockbox.v1.payload_service_pb2 import GetPayloadRequest
from yandex.cloud.lockbox.v1.payload_service_pb2_grpc import PayloadServiceStub

from util_yc_sa.types import SAContext, ServiceAccountObject


class YcSaLoader:
    """
    Унифицированный загрузчик контекста сервисного аккаунта.
    Источники ключа:
      • Lockbox (по secret_id или по folder_id+name через GetEx)
      • локальный JSON-файл authorized key
    Бутстрап-SDK должен иметь права на чтение Lockbox (если оттуда читаем).
    """

    def __init__(self, bootstrap_sdk: Optional[SDK] = None):
        # Если выполняемся в Functions/VM c привязанным SA — SDK() возьмет токен из метаданных рантайма.
        # Иначе можно передать сюда заранее инициализированный SDK с любым валидным способом аутентификации.
        self._bootstrap_sdk = bootstrap_sdk or SDK()

    # --------- ПУБЛИЧНЫЕ МЕТОДЫ ---------

    def from_lockbox_by_id(
        self,
        folder_id: str,
        sa_name: str,
        secret_id: str,
        key_field: str = "key.json",
        version_id: Optional[str] = None,
    ) -> SAContext:
        key_json = self._read_lockbox_payload(secret_id=secret_id, version_id=version_id)
        sa_key = self._extract_key_json(key_json, key_field)
        return self._build_context_from_key_json(folder_id, sa_name, sa_key)

    def from_lockbox_by_name(
        self,
        folder_id: str,
        sa_name: str,
        lockbox_folder_id: str,
        lockbox_secret_name: str,
        key_field: str = "key.json",
        version_id: Optional[str] = None,
    ) -> SAContext:
        """
        Вариант без знания secret_id: берем секрет по (folder_id, name) через GetEx.
        """
        # gRPC GetEx — вернет entries как map<string, bytes>
        # Делаем прямой вызов клиентом SDK
        stub = self._bootstrap_sdk.client(PayloadServiceStub)
        req = type("Req", (), {})()  # маленький хак, чтобы не тянуть сгенерированный GetExRequest
        # Сгенерированный класс доступен, но импорт путей может отличаться по версиям SDK.
        # Проще собрать через словарь:
        from yandex.cloud.lockbox.v1.payload_service_pb2 import GetExRequest, FolderAndName
        req = GetExRequest(folder_and_name=FolderAndName(folder_id=lockbox_folder_id, secret_name=lockbox_secret_name))
        if version_id:
            req.version_id = version_id
        resp = stub.GetEx(req)

        values: Dict[str, str] = {k: v.decode("utf-8") for k, v in resp.entries.items()}
        if key_field not in values:
            raise KeyError(f"В секрете '{lockbox_secret_name}' нет поля '{key_field}'. Есть: {list(values.keys())}")
        sa_key = json.loads(values[key_field])
        return self._build_context_from_key_json(folder_id, sa_name, sa_key)

    def from_local_file(self, folder_id: str, sa_name: str, key_file_path: str) -> SAContext:
        with open(key_file_path, "r", encoding="utf-8") as f:
            sa_key = json.load(f)
        return self._build_context_from_key_json(folder_id, sa_name, sa_key)

    # --------- ХЕЛПЕРЫ ДЛЯ YDB (опционально) ---------

    @staticmethod
    def make_ydb_credentials_from_sa_key_dict(sa_key: Dict) -> "ydb.iam.ServiceAccountCredentials":
        """
        YDB SDK в питоне принимает key-файл; готового from_dict нет.
        Поэтому пишем во временный файл и используем from_file — это соответствует доке.
        """
        import ydb, ydb.iam  # импорт здесь, чтобы не тащить в рантаймах без YDB
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "sa.json"
            p.write_text(json.dumps(sa_key), encoding="utf-8")
            return ydb.iam.ServiceAccountCredentials.from_file(str(p))  # оф. способ

    # --------- ВНУТРЕННЕЕ ---------

    def _read_lockbox_payload(self, secret_id: str, version_id: Optional[str]) -> Dict[str, str]:
        stub = self._bootstrap_sdk.client(PayloadServiceStub)
        req = GetPayloadRequest(secret_id=secret_id)
        if version_id:
            req.version_id = version_id
        payload = stub.Get(req)
        return {e.key: (e.text_value or e.binary_value.decode("utf-8")) for e in payload.entries}

    def _extract_key_json(self, lockbox_values: Dict[str, str], key_field: str) -> Dict:
        if key_field not in lockbox_values:
            raise KeyError(f"Поле '{key_field}' не найдено в Lockbox. Доступные: {list(lockbox_values.keys())}")
        return json.loads(lockbox_values[key_field])

    def _build_context_from_key_json(self, folder_id: str, sa_name: str, sa_key: Dict) -> SAContext:
        # 1) найдём SA по имени в папке — фильтр по name="..."
        iam = self._bootstrap_sdk.client(ServiceAccountServiceStub)
        resp = iam.List(ListServiceAccountsRequest(folder_id=folder_id, filter=f'name="{sa_name}"'))
        if len(resp.service_accounts) == 0:
            raise LookupError(f"Сервисный аккаунт name='{sa_name}' в папке '{folder_id}' не найден.")
        if len(resp.service_accounts) > 1:
            raise LookupError(f"Найдено несколько SA с именем '{sa_name}' в папке '{folder_id}'. Уточните имя.")
        sa = resp.service_accounts[0]

        # 2) создаём отдельный SDK под целевым SA по authorized key JSON
        target_sdk = SDK(service_account_key=sa_key)

        return SAContext(
            sdk=target_sdk,
            service_account=ServiceAccountObject(id=sa.id, name=sa.name, folder_id=sa.folder_id),
        )
