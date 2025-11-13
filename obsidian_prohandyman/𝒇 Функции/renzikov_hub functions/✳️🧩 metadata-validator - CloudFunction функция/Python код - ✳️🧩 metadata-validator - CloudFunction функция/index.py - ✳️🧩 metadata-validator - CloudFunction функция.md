```python
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import traceback
from typing import Any, Dict, List, Optional

import ydb

from utils import (
    parse_event, EventParseError,
    JsonLogger,
    ok, server_error, json_response,  # используем json_response для структурных 400
    loads_safe,
)
from utils.util_ydb.driver import get_session_pool
from utils.util_ydb.credentials import ydb_creds_from_env


# ---------- helpers ----------

def _require_env(name: str, fallback: Optional[str] = None) -> str:
    val = os.environ.get(name) or (os.environ.get(fallback) if fallback else None)
    if not val:
        raise RuntimeError(f"{name} not configured")
    return val


def _type_check(value: Any, expected_type: str) -> bool:
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    return True  # если тип не указан/неизвестен — не валим


def _validate_against_schema(data: Any, schema: Dict[str, Any], path: str = "$") -> List[str]:
    """Упрощённая валидация: type, required, properties, items, additionalProperties(false)."""
    errors: List[str] = []

    # type
    sch_type = schema.get("type")
    if sch_type and not _type_check(data, sch_type):
        errors.append(f"{path}: expected type {sch_type}")
        return errors  # без дальнейшего погружения

    # object: required + properties + additionalProperties
    if isinstance(data, dict):
        required = schema.get("required") or []
        for key in required:
            if key not in data:
                errors.append(f"{path}.{key}: is required")

        properties = schema.get("properties") or {}
        if isinstance(properties, dict):
            # additionalProperties: false
            addl = schema.get("additionalProperties")
            if addl is False:
                unknown = [k for k in data.keys() if k not in properties.keys()]
                for k in unknown:
                    errors.append(f"{path}.{k}: is not allowed")

            # рекурсивно валидируем известные свойства
            for key, subschema in properties.items():
                if key in data:
                    errors.extend(_validate_against_schema(data[key], subschema, f"{path}.{key}"))

    # array: items
    if isinstance(data, list) and isinstance(schema.get("items"), dict):
        item_schema = schema["items"]
        for idx, item in enumerate(data):
            errors.extend(_validate_against_schema(item, item_schema, f"{path}[{idx}]"))

    return errors


def _build_structured_400(message: str, errors: Optional[List[str]] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"message": message}
    if errors:
        payload["errors"] = errors
    return json_response(400, payload)


# ---------- handler ----------

def handler(event, context):
    # сначала парсим, потом создаём логгер с correlation id
    try:
        req = parse_event(event)
    except EventParseError as e:
        # логгер ещё не инициализирован — вернём 400 “как есть”
        return _build_structured_400(str(e))

    headers = req.get("headers") or {}
    corr_id = headers.get("x-correlation-id") or headers.get("x-correlationid") or None
    logger = JsonLogger(correlation_id=corr_id)

    logger.info("metadata_validator.invoked")

    body = req.get("body_dict") or {}
    schema_name = body.get("schema_name")
    entity_type = body.get("entity_type")
    metadata = body.get("metadata")

    # базовая валидация входа
    if not schema_name or not isinstance(schema_name, str):
        return _build_structured_400("schema_name is required and must be string")
    if not entity_type or not isinstance(entity_type, str):
        return _build_structured_400("entity_type is required and must be string")
    if metadata is None or not isinstance(metadata, dict):
        return _build_structured_400("metadata is required and must be object")

    # подключение к YDB (meta DB с fallback на основную пару)
    try:
        creds = ydb_creds_from_env()
        endpoint = _require_env("YDB_ENDPOINT_META", fallback="YDB_ENDPOINT")
        database = _require_env("YDB_DATABASE_META", fallback="YDB_DATABASE")
        pool = get_session_pool(endpoint, database, credentials=creds)
    except Exception as e:
        logger.error("db.connect_error", error=str(e))
        return server_error("Internal Server Error")

    def tx_body(session: ydb.Session):
        tx = session.transaction(ydb.SerializableReadWrite())

        # Читаем самую новую версию схемы
        query = f"""
            PRAGMA TablePathPrefix('{database}');
            DECLARE $schema_name AS Utf8;
            DECLARE $entity_type AS Utf8;
            SELECT schema_version, json_schema
            FROM schema_registry
            WHERE schema_name = $schema_name AND entity_type = $entity_type
            ORDER BY schema_version DESC
            LIMIT 1;
        """
        params = {"$schema_name": schema_name, "$entity_type": entity_type}

        rs = tx.execute(session.prepare(query), params)
        if not rs or not rs[0].rows:
            tx.rollback()
            return {"status": 400, "message": "Schema not found"}

        row = rs[0].rows[0]
        version = int(getattr(row, "schema_version"))
        schema_raw = getattr(row, "json_schema")

        # Аккуратно парсим JSON-схему
        _INVALID = object()
        schema_obj = None
        if isinstance(schema_raw, (str, bytes)):
            schema_obj = loads_safe(schema_raw, default=_INVALID)
        elif isinstance(schema_raw, dict):
            schema_obj = schema_raw
        else:
            schema_obj = _INVALID

        if schema_obj is _INVALID or not isinstance(schema_obj, dict):
            tx.rollback()
            return {"status": 500, "message": "Invalid schema JSON in registry"}

        # Валидируем metadata
        errors = _validate_against_schema(metadata, schema_obj)
        if errors:
            tx.rollback()
            return {"status": 400, "message": "Validation failed", "errors": errors}

        # Обогащаем metadata
        enriched = dict(metadata)
        enriched["__schema_name"] = schema_name
        enriched["__schema_version"] = version

        tx.commit()
        return {"status": 200, "version": version, "metadata": enriched}

    try:
        result = pool.retry_operation_sync(tx_body)
    except Exception as e:
        logger.error("tx.error", error=str(e), trace=traceback.format_exc())
        return server_error("Internal Server Error")

    status = result.get("status", 500)
    if status == 200:
        return ok({
            "valid": True,
            "schema_name": schema_name,
            "schema_version": result.get("version"),
            "metadata": result.get("metadata"),
        })
    if status == 400:
        return _build_structured_400(result.get("message", "Bad Request"), result.get("errors"))

    return server_error("Internal Server Error")
```