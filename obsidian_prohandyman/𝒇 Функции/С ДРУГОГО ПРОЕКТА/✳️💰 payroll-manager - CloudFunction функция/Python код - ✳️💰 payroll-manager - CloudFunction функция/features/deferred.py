# -*- coding: utf-8 -*-
from __future__ import annotations

import traceback

import ydb

from utils import JsonLogger, bad_request, created, server_error
from utils.util_log import YCLogger

from constants import EVENT_DEFERRED
from events_helper import create_event_entity
from handlers import (
    _ensure_employee_exists,
    _parse_iso_datetime,
    _read_firm_name,
    _read_supervisor_ids,
    _read_user_full_name,
    _send_notice_safe,
    _server_now_iso,
)


def handle_deferred_create(
    *,
    body: dict,
    firm_id: str,
    caller_user_id: str,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    logger: JsonLogger,
    hlog: YCLogger,
):
    user_id = body.get("user_id")
    deferred_until_raw = body.get("deferred_until")

    if not isinstance(user_id, str) or not user_id.strip():
        return bad_request("user_id is required")

    deferred_until = _parse_iso_datetime(deferred_until_raw)
    if not deferred_until:
        return bad_request("deferred_until must be a valid ISO datetime")
    event_at = _server_now_iso()

    user_id = user_id.strip()

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
        "deferred_until": deferred_until,
        "event_at": event_at,
    }

    try:
        event_id = create_event_entity(user_id, EVENT_DEFERRED, payload, logger, firm_id=firm_id, schema_version=3)
    except Exception as e:
        logger.error("payroll_manager.deferred.event_failed", error=str(e), trace=traceback.format_exc())
        hlog.exception("payroll_manager.deferred.event_failed", error=str(e))
        return server_error("Event generation failed")
    try:
        worker_name = _read_user_full_name(
            firms_pool=firms_pool,
            firms_database=firms_database,
            user_id=user_id,
        ) or "Рабочий"
        _send_notice_safe(
            logger=logger,
            hlog=hlog,
            user_id=user_id,
            notice_type="your_payout_deferred",
            data={
                "firm_id": firm_id,
                "firm_name": _read_firm_name(
                    firms_pool=firms_pool,
                    firms_database=firms_database,
                    firm_id=firm_id,
                )
                or f"Фирма {firm_id}",
                "user_id": user_id,
                "deferred_until": deferred_until,
            },
        )
        for supervisor_user_id in _read_supervisor_ids(
            firms_pool=firms_pool,
            firms_database=firms_database,
            firm_id=firm_id,
        ):
            if supervisor_user_id == user_id:
                continue
            _send_notice_safe(
                logger=logger,
                hlog=hlog,
                user_id=supervisor_user_id,
                notice_type="worker_payout_deferred",
                data={
                    "firm_id": firm_id,
                    "user_id": user_id,
                    "worker_name": worker_name,
                    "deferred_until": deferred_until,
                },
            )
    except Exception as e:
        logger.error("payroll_manager.deferred.notice_failed", error=str(e), trace=traceback.format_exc())
        hlog.exception("payroll_manager.deferred.notice_failed", error=str(e))

    return created(
        {
            "message": "Deferred payout created",
            "event_id": event_id,
            "firm_id": firm_id,
            "user_id": user_id,
        }
    )
