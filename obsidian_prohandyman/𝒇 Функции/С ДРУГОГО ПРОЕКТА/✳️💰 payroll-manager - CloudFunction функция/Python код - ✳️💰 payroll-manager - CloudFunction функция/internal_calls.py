# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import uuid
from typing import Any

from utils import JsonLogger, build_internal_http_event, build_internal_invocation_context
from utils.util_invoke.invoke import invoke_function

from sa import get_iam_token

FUNCTION_HOST = "functions.yandexcloud.net"
SERVICE_NAME = "payroll-manager"


def _invoke_internal_event(
    *,
    fn_id: str,
    path: str,
    body: dict,
    request_schema_hash: str,
    response_schema_hash: str,
    logger: JsonLogger,
    timeout_s: int = 60,
) -> dict:
    iam_token = get_iam_token(logger)
    if not iam_token:
        raise RuntimeError(f"Failed to get IAM token for {path} invoke")

    internal_context = build_internal_invocation_context(
        service_name=SERVICE_NAME,
        trace_id=str(uuid.uuid4()),
    )
    event = build_internal_http_event(
        path=path,
        body=body,
        internal_context=internal_context,
        request_schema_hash=request_schema_hash,
        response_schema_hash=response_schema_hash,
    )
    logger.info(
        "payroll_manager.internal_invoke.start",
        target_path=path,
        fn_id=fn_id,
        body_keys=sorted(body.keys()),
        has_request_schema_hash=bool(request_schema_hash),
        has_response_schema_hash=bool(response_schema_hash),
    )
    resp = invoke_function(
        target=f"https://{FUNCTION_HOST}/{fn_id}",
        json_payload=event,
        auth_headers={"Authorization": f"Bearer {iam_token}"},
        allow_hosts=(FUNCTION_HOST,),
        parse_json=True,
        timeout_s=timeout_s,
    )
    logger.info(
        "payroll_manager.internal_invoke.result",
        target_path=path,
        fn_id=fn_id,
        ok=bool(resp.get("ok")),
        status_code=resp.get("status_code"),
        meta=resp.get("meta"),
    )
    return resp


def call_metadata_validator(schema_name: str, entity_type: str, metadata: Any, logger: JsonLogger) -> Any:
    fn_id = os.environ.get("FN_METADATA_VALIDATOR")
    if not fn_id:
        raise RuntimeError("FN_METADATA_VALIDATOR is not configured")

    req_hash = os.environ.get("METADATA_VALIDATOR_REQUEST_SCHEMA_HASH")
    res_hash = os.environ.get("METADATA_VALIDATOR_RESPONSE_SCHEMA_HASH")
    if not req_hash or not res_hash:
        raise RuntimeError("METADATA_VALIDATOR_REQUEST_SCHEMA_HASH/METADATA_VALIDATOR_RESPONSE_SCHEMA_HASH is required")

    logger.info(
        "payroll_manager.metadata_validator.start",
        schema_name=schema_name,
        entity_type=entity_type,
        metadata_type=type(metadata).__name__,
        metadata_keys=sorted(metadata.keys()) if isinstance(metadata, dict) else None,
    )
    resp = _invoke_internal_event(
        fn_id=fn_id,
        path="/metadata/validate",
        body={
            "schema_name": schema_name,
            "entity_type": entity_type,
            "metadata": metadata,
        },
        request_schema_hash=req_hash,
        response_schema_hash=res_hash,
        logger=logger,
        timeout_s=60,
    )

    if not resp.get("ok"):
        status = resp.get("status_code")
        payload = resp.get("json") or {}
        logger.warn(
            "payroll_manager.metadata_validator.http_error",
            schema_name=schema_name,
            entity_type=entity_type,
            status=status,
            payload=payload,
            meta=resp.get("meta"),
        )
        if status and 400 <= status < 500:
            errors = payload.get("errors")
            if isinstance(errors, list) and errors:
                raise ValueError(str(errors[0]))
            msg = payload.get("message") or (payload.get("error") or {}).get("message")
            raise ValueError(msg or "Metadata validation failed")
        logger.error("payroll_manager.metadata_validator_failed", status=status, meta=resp.get("meta"))
        raise RuntimeError("Metadata validator call failed")

    out = resp.get("json") or {}
    if not out.get("valid"):
        errors = out.get("errors") or ["Metadata validation failed"]
        logger.warn(
            "payroll_manager.metadata_validator.invalid",
            schema_name=schema_name,
            entity_type=entity_type,
            errors=errors,
        )
        raise ValueError(str(errors[0]))

    validated = out.get("metadata")
    if validated is None:
        logger.info(
            "payroll_manager.metadata_validator.success",
            schema_name=schema_name,
            entity_type=entity_type,
            returned_type=type(metadata).__name__,
        )
        return metadata

    # Backward-compat: old metadata-validator wrapped non-object values as {"__value": ...}
    if not isinstance(metadata, dict) and isinstance(validated, dict) and "__value" in validated:
        logger.info(
            "payroll_manager.metadata_validator.success",
            schema_name=schema_name,
            entity_type=entity_type,
            returned_type=type(validated.get("__value")).__name__,
        )
        return validated.get("__value")

    # Do not leak service keys into stored/returned data
    if isinstance(validated, dict):
        sanitized = {k: v for k, v in validated.items() if not (isinstance(k, str) and k.startswith("__schema_"))}
        logger.info(
            "payroll_manager.metadata_validator.success",
            schema_name=schema_name,
            entity_type=entity_type,
            returned_type=type(sanitized).__name__,
        )
        return sanitized

    logger.info(
        "payroll_manager.metadata_validator.success",
        schema_name=schema_name,
        entity_type=entity_type,
        returned_type=type(validated).__name__,
    )
    return validated
