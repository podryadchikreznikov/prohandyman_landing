from __future__ import annotations
from dataclasses import dataclass

@dataclass
class ServiceAccountObject:
    id: str
    name: str
    folder_id: str

@dataclass
class SAContext:
    """Контекст, под которым можно дергать YC API."""
    sdk: "yandexcloud.SDK"          # аутентифицированный SDK под целевым SA
    service_account: ServiceAccountObject
