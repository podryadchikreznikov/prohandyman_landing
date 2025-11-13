"""
Утилиты для работы с сервисными аккаунтами Yandex Cloud.

Позволяют загружать контекст сервисного аккаунта из различных источников:
- Lockbox (по secret_id или по folder_id+name)
- Локальный JSON-файл authorized key
"""

from util_yc_sa.loader import YcSaLoader
from util_yc_sa.types import SAContext, ServiceAccountObject

__all__ = [
    "YcSaLoader",
    "SAContext", 
    "ServiceAccountObject",
]
