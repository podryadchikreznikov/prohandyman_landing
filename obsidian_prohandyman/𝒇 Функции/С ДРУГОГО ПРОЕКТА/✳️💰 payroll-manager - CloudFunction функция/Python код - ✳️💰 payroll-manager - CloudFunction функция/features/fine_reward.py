# -*- coding: utf-8 -*-
from __future__ import annotations

import traceback
from typing import Any, Dict, Optional, Tuple

import ydb

from utils import JsonLogger, bad_request, created, server_error
from utils.util_log import YCLogger

from common import is_uuid
from constants import EVENT_FINE, EVENT_REWARD
from events_helper import create_event_entity
from handlers import (
    _ensure_employee_exists,
    _format_money_kopeks,
    _parse_json_value,
    _send_notice_safe,
    _server_now_iso,
    _validate_field_type,
)


def _parse_reward_linkage(body: dict) -> Tuple[Dict[str, Any], Optional[str]]:
    source_kind_raw = body.get("source_kind")
    source_appeal_id_raw = body.get("source_appeal_id")
    source_event_type_raw = body.get("source_event_type")
    source_event_id_raw = body.get("source_event_id")

    source_kind = None
    if source_kind_raw is not None:
        if not isinstance(source_kind_raw, str) or not source_kind_raw.strip():
            return {}, "source_kind must be a non-empty string"
        source_kind = source_kind_raw.strip().lower()
        if source_kind not in {"appeal_compensation"}:
            return {}, "source_kind must be 'appeal_compensation'"

    source_appeal_id = None
    if source_appeal_id_raw is not None:
        if not isinstance(source_appeal_id_raw, str) or not source_appeal_id_raw.strip():
            return {}, "source_appeal_id must be a non-empty string"
        source_appeal_id = source_appeal_id_raw.strip()
        if not is_uuid(source_appeal_id):
            return {}, "source_appeal_id must be a valid UUID"

    source_event_type = None
    if source_event_type_raw is not None:
        if not isinstance(source_event_type_raw, str) or not source_event_type_raw.strip():
            return {}, "source_event_type must be a non-empty string"
        source_event_type = source_event_type_raw.strip().lower()
        if source_event_type != "fine":
            return {}, "source_event_type must be 'fine'"

    source_event_id = None
    if source_event_id_raw is not None:
        if not isinstance(source_event_id_raw, str) or not source_event_id_raw.strip():
            return {}, "source_event_id must be a non-empty string"
        source_event_id = source_event_id_raw.strip()
        if not is_uuid(source_event_id):
            return {}, "source_event_id must be a valid UUID"

    has_source_fields = any(v is not None for v in [source_appeal_id, source_event_type, source_event_id])
    if has_source_fields and source_kind is None:
        return {}, "source_kind is required when source_* fields are provided"

    if source_kind == "appeal_compensation":
        if not source_appeal_id:
            return {}, "source_appeal_id is required for source_kind=appeal_compensation"
        if not source_event_id:
            return {}, "source_event_id is required for source_kind=appeal_compensation"
        source_event_type = source_event_type or "fine"
        if source_event_type != "fine":
            return {}, "source_event_type must be 'fine' for source_kind=appeal_compensation"

    payload: Dict[str, Any] = {}
    if source_kind is not None:
        payload["source_kind"] = source_kind
    if source_appeal_id is not None:
        payload["source_appeal_id"] = source_appeal_id
    if source_event_type is not None:
        payload["source_event_type"] = source_event_type
    if source_event_id is not None:
        payload["source_event_id"] = source_event_id
    return payload, None


def _handle_fine_reward(
    *,
    body: dict,
    firm_id: str,
    caller_user_id: str,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    logger: JsonLogger,
    hlog: YCLogger,
    event_type: str,
    success_message: str,
):
    user_id = body.get("user_id")
    object_id = body.get("object_id")
    theme = body.get("theme")
    amount_kopeks = body.get("amount_kopeks")
    message = body.get("message")

    if not isinstance(user_id, str) or not user_id.strip():
        return bad_request("user_id is required")
    if not is_uuid(user_id.strip()):
        return bad_request("user_id must be a valid UUID")
    if not isinstance(object_id, str) or not object_id.strip():
        return bad_request("object_id is required")
    if not is_uuid(object_id.strip()):
        return bad_request("object_id must be a valid UUID")
    if not isinstance(theme, str) or not theme.strip():
        return bad_request("theme is required")
    if not isinstance(amount_kopeks, int) or amount_kopeks < 0:
        return bad_request("amount_kopeks must be a non-negative integer")
    event_at = _server_now_iso()

    attachments_json = _parse_json_value(body.get("attachments_json"))
    if attachments_json is not None and not isinstance(attachments_json, list):
        return bad_request("attachments_json must be an array")

    try:
        if attachments_json is not None:
            attachments_json = _validate_field_type("attachments_json", attachments_json, logger)
    except ValueError as e:
        return bad_request(str(e))
    except Exception:
        logger.error("payroll_manager.metadata_validation_failed", trace=traceback.format_exc())
        return server_error("Metadata validation failed")

    if message is not None and not isinstance(message, str):
        return bad_request("message must be a string")

    user_id = user_id.strip()
    object_id = object_id.strip()

    exists_error = _ensure_employee_exists(
        firm_id=firm_id,
        user_id=user_id,
        firms_pool=firms_pool,
        firms_database=firms_database,
        logger=logger,
        hlog=hlog,
    )
    if exists_error:
        return exists_error

    payload = {
        "firm_id": firm_id,
        "user_id": user_id,
        "object_id": object_id,
        "theme": theme.strip(),
        "amount_kopeks": amount_kopeks,
        "message": message,
        "attachments_json": attachments_json,
        "event_at": event_at,
    }
    schema_version = 2
    if event_type == EVENT_REWARD:
        reward_linkage, linkage_error = _parse_reward_linkage(body)
        if linkage_error:
            return bad_request(linkage_error)
        payload.update(reward_linkage)
        schema_version = 3

    try:
        event_id = create_event_entity(user_id, event_type, payload, logger, firm_id=firm_id, schema_version=schema_version)
    except Exception as e:
        logger.error("payroll_manager.event_failed", error=str(e), trace=traceback.format_exc())
        hlog.exception("payroll_manager.event_failed", error=str(e))
        return server_error("Event generation failed")
    try:
        if event_type == EVENT_FINE:
            _send_notice_safe(
                logger=logger,
                hlog=hlog,
                user_id=user_id,
                notice_type="you_received_fine",
                data={
                    "firm_id": firm_id,
                    "user_id": user_id,
                    "object_id": object_id,
                    "fine_id": event_id,
                    "amount_text": _format_money_kopeks(amount_kopeks),
                    "reason": theme.strip(),
                },
            )
        elif event_type == EVENT_REWARD:
            _send_notice_safe(
                logger=logger,
                hlog=hlog,
                user_id=user_id,
                notice_type="you_received_reward",
                data={
                    "firm_id": firm_id,
                    "user_id": user_id,
                    "object_id": object_id,
                    "reward_id": event_id,
                    "amount_text": _format_money_kopeks(amount_kopeks),
                    "comment": (message or "").strip() or theme.strip(),
                },
            )
    except Exception as e:
        logger.error("payroll_manager.fine_reward.notice_failed", error=str(e), trace=traceback.format_exc())
        hlog.exception("payroll_manager.fine_reward.notice_failed", error=str(e))

    return created(
        {
            "message": success_message,
            "event_id": event_id,
            "firm_id": firm_id,
            "user_id": user_id,
        }
    )


def handle_fine_create(
    *,
    body: dict,
    firm_id: str,
    caller_user_id: str,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    logger: JsonLogger,
    hlog: YCLogger,
):
    return _handle_fine_reward(
        body=body,
        firm_id=firm_id,
        caller_user_id=caller_user_id,
        firms_pool=firms_pool,
        firms_database=firms_database,
        logger=logger,
        hlog=hlog,
        event_type=EVENT_FINE,
        success_message="Fine created",
    )


def handle_reward_create(
    *,
    body: dict,
    firm_id: str,
    caller_user_id: str,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    logger: JsonLogger,
    hlog: YCLogger,
):
    return _handle_fine_reward(
        body=body,
        firm_id=firm_id,
        caller_user_id=caller_user_id,
        firms_pool=firms_pool,
        firms_database=firms_database,
        logger=logger,
        hlog=hlog,
        event_type=EVENT_REWARD,
        success_message="Reward created",
    )
