from __future__ import annotations

import os
import threading
from typing import Any, Dict, Optional, Tuple

import ydb

_DRIVER_CACHE: Dict[Tuple[str, str, str], ydb.Driver] = {}
_POOL_CACHE: Dict[Tuple[str, str, str], ydb.SessionPool] = {}
_CACHE_LOCK = threading.Lock()


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Environment variable '{name}' is not set or empty")
    return value


def _resolve_sa_key(sa_key_file: Optional[str], sa_key_var: Optional[str]) -> str:
    if sa_key_file:
        return sa_key_file
    env_name = sa_key_var or "SA_KEY_FILE"
    return _require_env(env_name)


def _build_key(endpoint: str, database: str, sa_key_file: str) -> Tuple[str, str, str]:
    return endpoint, database, sa_key_file


def get_driver(
    endpoint: str,
    database: str,
    *,
    sa_key_file: Optional[str] = None,
    sa_key_var: Optional[str] = None,
    wait_timeout_sec: float = 5.0,
    credentials: Optional[Any] = None,
) -> ydb.Driver:
    """
    Lazily creates (and caches) a YDB driver for the provided endpoint/database pair.

    If ``credentials`` is provided the driver will not be cached.
    """
    if credentials is not None:
        driver = ydb.Driver(endpoint=endpoint, database=database, credentials=credentials)
        driver.wait(timeout=wait_timeout_sec, fail_fast=True)
        return driver

    resolved_sa = _resolve_sa_key(sa_key_file, sa_key_var)
    cache_key = _build_key(endpoint, database, resolved_sa)

    driver = _DRIVER_CACHE.get(cache_key)
    if driver:
        return driver

    with _CACHE_LOCK:
        driver = _DRIVER_CACHE.get(cache_key)
        if driver:
            return driver
        creds = ydb.iam.ServiceAccountCredentials.from_file(resolved_sa)
        driver = ydb.Driver(endpoint=endpoint, database=database, credentials=creds)
        driver.wait(timeout=wait_timeout_sec, fail_fast=True)
        _DRIVER_CACHE[cache_key] = driver
        return driver


def get_session_pool(
    endpoint: str,
    database: str,
    *,
    sa_key_file: Optional[str] = None,
    sa_key_var: Optional[str] = None,
    wait_timeout_sec: float = 5.0,
    credentials: Optional[Any] = None,
) -> ydb.SessionPool:
    """
    Returns a cached session pool bound to a cached driver (unless explicit credentials supplied).
    """
    if credentials is not None:
        driver = get_driver(endpoint, database, sa_key_file=sa_key_file, sa_key_var=sa_key_var, wait_timeout_sec=wait_timeout_sec, credentials=credentials)
        return ydb.SessionPool(driver)

    resolved_sa = _resolve_sa_key(sa_key_file, sa_key_var)
    cache_key = _build_key(endpoint, database, resolved_sa)

    pool = _POOL_CACHE.get(cache_key)
    if pool:
        return pool

    with _CACHE_LOCK:
        pool = _POOL_CACHE.get(cache_key)
        if pool:
            return pool
        driver = get_driver(endpoint, database, sa_key_file=resolved_sa, wait_timeout_sec=wait_timeout_sec)
        pool = ydb.SessionPool(driver)
        _POOL_CACHE[cache_key] = pool
        return pool


def get_driver_from_env(
    endpoint_var: str = "YDB_ENDPOINT",
    database_var: str = "YDB_DATABASE",
    *,
    sa_key_var: Optional[str] = "SA_KEY_FILE",
    wait_timeout_sec: float = 5.0,
) -> ydb.Driver:
    endpoint = _require_env(endpoint_var)
    database = _require_env(database_var)
    sa_key = _resolve_sa_key(None, sa_key_var)
    return get_driver(endpoint, database, sa_key_file=sa_key, wait_timeout_sec=wait_timeout_sec)


def get_session_pool_from_env(
    endpoint_var: str = "YDB_ENDPOINT",
    database_var: str = "YDB_DATABASE",
    *,
    sa_key_var: Optional[str] = "SA_KEY_FILE",
    wait_timeout_sec: float = 5.0,
) -> ydb.SessionPool:
    endpoint = _require_env(endpoint_var)
    database = _require_env(database_var)
    sa_key = _resolve_sa_key(None, sa_key_var)
    return get_session_pool(endpoint, database, sa_key_file=sa_key, wait_timeout_sec=wait_timeout_sec)


__all__ = (
    "get_driver",
    "get_session_pool",
    "get_driver_from_env",
    "get_session_pool_from_env",
)