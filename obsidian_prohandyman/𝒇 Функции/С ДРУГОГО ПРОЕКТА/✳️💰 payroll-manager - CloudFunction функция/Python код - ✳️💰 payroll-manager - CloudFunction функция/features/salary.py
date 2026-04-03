# -*- coding: utf-8 -*-
from __future__ import annotations

import traceback
import uuid
from typing import Any, Dict, List, Optional

import ydb

from utils import JsonLogger, bad_request, not_found, now_utc, ok, parse_iso_utc, server_error
from utils.util_log import YCLogger

from common import is_uuid
from handlers import (
    _ensure_employee_exists,
    _parse_date,
    _parse_iso_datetime,
    _read_firm_name,
    _send_notice_safe,
    _to_iso_date,
    _to_iso_utc,
)


def _read_employee_salary_snapshot(
    *,
    notices_pool: ydb.SessionPool,
    notices_database: str,
    firm_id: str,
    user_id: str,
    active_only: bool = False,
    as_of: Optional[str] = None,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    def _tx(session: ydb.Session):
        where_parts = [
            "firm_id = $firm_id",
            "user_id = $user_id",
        ]
        if as_of:
            where_parts.append("(effective_from IS NULL OR effective_from <= $as_of)")
            where_parts.append("(deleted_at IS NULL OR deleted_at > $as_of)")
        elif active_only:
            where_parts.append('(status = "active" AND deleted_at IS NULL)')
        q = f"""
            PRAGMA TablePathPrefix('{notices_database}');
            DECLARE $firm_id AS Utf8;
            DECLARE $user_id AS Utf8;
            {"DECLARE $as_of AS Timestamp;" if as_of else ""}
            SELECT salary_id, user_id, firm_id, amount, payout_date, last_payout_at, status, effective_from, deleted_at, created_at, updated_at
            FROM employee_salary
            WHERE {" AND ".join(where_parts)}
            ORDER BY payout_date ASC, effective_from ASC, deleted_at ASC, created_at ASC;
        """
        params = {"$firm_id": firm_id, "$user_id": user_id}
        if as_of:
            params["$as_of"] = parse_iso_utc(as_of)
        rs = session.transaction(ydb.OnlineReadOnly()).execute(
            session.prepare(q),
            params,
            commit_tx=True,
        )
        rows = rs[0].rows if rs and rs[0].rows else []
        for row in rows:
            salary_id = str(getattr(row, "salary_id", "") or "").strip()
            if not salary_id:
                continue
            out.append(
                {
                    "salary_id": salary_id,
                    "user_id": str(getattr(row, "user_id", "") or "").strip() or user_id,
                    "firm_id": str(getattr(row, "firm_id", "") or "").strip() or firm_id,
                    "amount_kopeks": int(getattr(row, "amount", 0) or 0),
                    "payout_date": _to_iso_date(getattr(row, "payout_date", None)),
                    "last_payout_at": _to_iso_utc(getattr(row, "last_payout_at", None)),
                    "status": str(getattr(row, "status", "") or "").strip().lower() or "active",
                    "effective_from": _to_iso_utc(getattr(row, "effective_from", None)),
                    "deleted_at": _to_iso_utc(getattr(row, "deleted_at", None)),
                    "created_at": _to_iso_utc(getattr(row, "created_at", None)),
                    "updated_at": _to_iso_utc(getattr(row, "updated_at", None)),
                }
            )

    notices_pool.retry_operation_sync(_tx)
    return out


def _update_salary_last_payout_at(
    *,
    notices_pool: ydb.SessionPool,
    notices_database: str,
    firm_id: str,
    salary_payment_items: List[Dict[str, Any]],
):
    latest_paid_at_by_salary_id: Dict[str, Any] = {}
    for item in salary_payment_items:
        salary_id = str(item.get("salary_id") or "").strip()
        paid_at_raw = _parse_iso_datetime(item.get("paid_at"))
        if not salary_id or not paid_at_raw:
            continue
        paid_at = parse_iso_utc(paid_at_raw)
        current_latest = latest_paid_at_by_salary_id.get(salary_id)
        if current_latest is None or paid_at > current_latest:
            latest_paid_at_by_salary_id[salary_id] = paid_at

    if not latest_paid_at_by_salary_id:
        return

    def _tx(session: ydb.Session):
        tx = session.transaction(ydb.SerializableReadWrite())
        tx.begin()
        q = f"""
            PRAGMA TablePathPrefix('{notices_database}');
            DECLARE $salary_id AS Utf8;
            DECLARE $firm_id AS Utf8;
            DECLARE $last_payout_at AS Timestamp;
            UPDATE employee_salary
            SET last_payout_at = $last_payout_at
            WHERE salary_id = $salary_id AND firm_id = $firm_id;
        """
        prepared = session.prepare(q)
        for salary_id, paid_at in latest_paid_at_by_salary_id.items():
            tx.execute(
                prepared,
                {
                    "$salary_id": salary_id,
                    "$firm_id": firm_id,
                    "$last_payout_at": paid_at,
                },
            )
        tx.commit()

    notices_pool.retry_operation_sync(_tx)


def _build_salary_change_notice_data(
    *,
    firm_id: str,
    user_id: str,
    firm_name: str,
    salary_snapshot: List[Dict[str, Any]],
    effective_from: Optional[str],
    action_text: str,
    status_text: str,
) -> Dict[str, Any]:
    active_records_count = 0
    deleted_records_count = 0
    for item in salary_snapshot:
        status = str(item.get("status", "") or "").strip().lower()
        if status == "deleted":
            deleted_records_count += 1
        else:
            active_records_count += 1

    return {
        "firm_id": firm_id,
        "firm_name": firm_name,
        "user_id": user_id,
        "salary_text": "Изменен график заработной платы",
        "employee_salary_snapshot": salary_snapshot,
        "effective_from": effective_from,
        "action_text": action_text,
        "status_text": status_text,
        "active_records_count": active_records_count,
        "deleted_records_count": deleted_records_count,
    }


def handle_salary_upsert(
    *,
    body: dict,
    firm_id: str,
    caller_user_id: str,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    notices_pool: ydb.SessionPool,
    notices_database: str,
    logger: JsonLogger,
    hlog: YCLogger,
):
    salary_id = body.get("salary_id")
    user_id = body.get("user_id")
    amount_kopeks = body.get("amount_kopeks")
    payout_date_raw = body.get("payout_date")
    effective_from_raw = body.get("effective_from")

    if not isinstance(user_id, str) or not user_id.strip():
        return bad_request("user_id is required")
    if not is_uuid(user_id.strip()):
        return bad_request("user_id must be a valid UUID")
    if not is_uuid(user_id.strip()):
        return bad_request("user_id must be a valid UUID")
    if not isinstance(amount_kopeks, int) or amount_kopeks < 0:
        return bad_request("amount_kopeks must be a non-negative integer")

    payout_date = _parse_date(payout_date_raw)
    if not payout_date:
        return bad_request("payout_date must be a valid date (YYYY-MM-DD)")
    effective_from = _parse_iso_datetime(effective_from_raw)
    if not effective_from:
        return bad_request("effective_from must be a valid ISO datetime")

    user_id = user_id.strip()
    salary_id = salary_id.strip() if isinstance(salary_id, str) and salary_id.strip() else None
    if salary_id and not is_uuid(salary_id):
        return bad_request("salary_id must be a valid UUID")

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

    now = now_utc()

    def _tx(session: ydb.Session) -> Dict[str, Any]:
        tx = session.transaction(ydb.SerializableReadWrite())

        if salary_id:
            select_q = f"""
                PRAGMA TablePathPrefix('{notices_database}');
                DECLARE $salary_id AS Utf8;
                DECLARE $firm_id AS Utf8;
                SELECT salary_id
                FROM employee_salary
                WHERE salary_id = $salary_id AND firm_id = $firm_id
                LIMIT 1;
            """
            rs = tx.execute(session.prepare(select_q), {"$salary_id": salary_id, "$firm_id": firm_id})
            if not rs or not rs[0].rows:
                tx.rollback()
                return {"status": "NOT_FOUND"}

            update_q = f"""
                PRAGMA TablePathPrefix('{notices_database}');
                DECLARE $salary_id AS Utf8;
                DECLARE $firm_id AS Utf8;
                DECLARE $amount AS Int64;
                DECLARE $payout_date AS Date;
                DECLARE $effective_from AS Timestamp;
                DECLARE $updated_at AS Timestamp;
                UPDATE employee_salary
                SET amount = $amount, payout_date = $payout_date, status = "active", effective_from = $effective_from, deleted_at = NULL, updated_at = $updated_at
                WHERE salary_id = $salary_id AND firm_id = $firm_id;
            """
            tx.execute(
                session.prepare(update_q),
                {
                    "$salary_id": salary_id,
                    "$firm_id": firm_id,
                    "$amount": amount_kopeks,
                    "$payout_date": payout_date,
                    "$effective_from": parse_iso_utc(effective_from),
                    "$updated_at": now,
                },
            )
            tx.commit()
            return {"status": "UPDATED", "salary_id": salary_id}

        new_salary_id = str(uuid.uuid4())
        insert_q = f"""
            PRAGMA TablePathPrefix('{notices_database}');
            DECLARE $salary_id AS Utf8;
            DECLARE $user_id AS Utf8;
            DECLARE $firm_id AS Utf8;
            DECLARE $amount AS Int64;
            DECLARE $payout_date AS Date;
            DECLARE $effective_from AS Timestamp;
            DECLARE $created_at AS Timestamp;
            DECLARE $updated_at AS Timestamp;
            UPSERT INTO employee_salary (
                salary_id,
                user_id,
                firm_id,
                amount,
                payout_date,
                last_payout_at,
                status,
                effective_from,
                deleted_at,
                created_at,
                updated_at
            ) VALUES (
                $salary_id,
                $user_id,
                $firm_id,
                $amount,
                $payout_date,
                NULL,
                "active",
                $effective_from,
                NULL,
                $created_at,
                $updated_at
            );
        """
        tx.execute(
            session.prepare(insert_q),
            {
                "$salary_id": new_salary_id,
                "$user_id": user_id,
                "$firm_id": firm_id,
                "$amount": amount_kopeks,
                "$payout_date": payout_date,
                "$effective_from": parse_iso_utc(effective_from),
                "$created_at": now,
                "$updated_at": now,
            },
        )
        tx.commit()
        return {"status": "CREATED", "salary_id": new_salary_id}

    try:
        result = notices_pool.retry_operation_sync(_tx)
    except Exception as e:
        logger.error("payroll_manager.salary_upsert.tx_error", error=str(e), trace=traceback.format_exc())
        hlog.exception("payroll_manager.salary_upsert.tx_error", error=str(e))
        return server_error("Internal Server Error")

    if result.get("status") == "NOT_FOUND":
        return not_found("Salary record not found")

    try:
        logger.info(
            "payroll_manager.salary_upsert.notice_start",
            firm_id=firm_id,
            user_id=user_id,
            salary_id=result.get("salary_id"),
            amount_kopeks=amount_kopeks,
        )
        notice_result = _send_notice_safe(
            logger=logger,
            hlog=hlog,
            user_id=user_id,
            notice_type="your_salary_changed",
            data=_build_salary_change_notice_data(
                firm_id=firm_id,
                user_id=user_id,
                firm_name=_read_firm_name(
                    firms_pool=firms_pool,
                    firms_database=firms_database,
                    firm_id=firm_id,
                )
                or f"Фирма {firm_id}",
                salary_snapshot=_read_employee_salary_snapshot(
                    notices_pool=notices_pool,
                    notices_database=notices_database,
                    firm_id=firm_id,
                    user_id=user_id,
                ),
                effective_from=effective_from,
                action_text="Запись зарплаты сохранена",
                status_text="active",
            ),
        )
        logger.info(
            "payroll_manager.salary_upsert.notice_done",
            firm_id=firm_id,
            user_id=user_id,
            salary_id=result.get("salary_id"),
            notice_result=notice_result,
        )
    except Exception as e:
        logger.error("payroll_manager.salary_upsert.notice_failed", error=str(e), trace=traceback.format_exc())
        hlog.exception("payroll_manager.salary_upsert.notice_failed", error=str(e))

    return ok(
        {
            "message": "Salary saved",
            "firm_id": firm_id,
            "salary_id": result.get("salary_id"),
            "user_id": user_id,
        }
    )


def handle_salary_delete(
    *,
    body: dict,
    firm_id: str,
    caller_user_id: str,
    firms_pool: ydb.SessionPool,
    firms_database: str,
    notices_pool: ydb.SessionPool,
    notices_database: str,
    logger: JsonLogger,
    hlog: YCLogger,
):
    salary_id = body.get("salary_id")
    user_id = body.get("user_id")

    if not isinstance(user_id, str) or not user_id.strip():
        return bad_request("user_id is required")
    if not is_uuid(user_id.strip()):
        return bad_request("user_id must be a valid UUID")
    if not isinstance(salary_id, str) or not salary_id.strip():
        return bad_request("salary_id is required")
    if not is_uuid(salary_id.strip()):
        return bad_request("salary_id must be a valid UUID")

    user_id = user_id.strip()
    salary_id = salary_id.strip()

    def _tx(session: ydb.Session) -> Dict[str, Any]:
        tx = session.transaction(ydb.SerializableReadWrite())

        select_q = f"""
            PRAGMA TablePathPrefix('{notices_database}');
            DECLARE $salary_id AS Utf8;
            DECLARE $firm_id AS Utf8;
            DECLARE $user_id AS Utf8;
            SELECT salary_id
            FROM employee_salary
            WHERE salary_id = $salary_id AND firm_id = $firm_id AND user_id = $user_id
            LIMIT 1;
        """
        rs = tx.execute(
            session.prepare(select_q),
            {"$salary_id": salary_id, "$firm_id": firm_id, "$user_id": user_id},
        )
        if not rs or not rs[0].rows:
            tx.rollback()
            return {"status": "NOT_FOUND"}

        delete_q = f"""
            PRAGMA TablePathPrefix('{notices_database}');
            DECLARE $salary_id AS Utf8;
            DECLARE $firm_id AS Utf8;
            DECLARE $user_id AS Utf8;
            DECLARE $deleted_at AS Timestamp;
            DECLARE $updated_at AS Timestamp;
            UPDATE employee_salary
            SET status = "deleted", deleted_at = $deleted_at, updated_at = $updated_at
            WHERE salary_id = $salary_id AND firm_id = $firm_id AND user_id = $user_id;
        """
        tx.execute(
            session.prepare(delete_q),
            {
                "$salary_id": salary_id,
                "$firm_id": firm_id,
                "$user_id": user_id,
                "$deleted_at": now_utc(),
                "$updated_at": now_utc(),
            },
        )
        tx.commit()
        return {"status": "DELETED"}

    try:
        result = notices_pool.retry_operation_sync(_tx)
    except Exception as e:
        logger.error(
            "payroll_manager.salary_delete.tx_error",
            error=str(e),
            trace=traceback.format_exc(),
        )
        hlog.exception("payroll_manager.salary_delete.tx_error", error=str(e))
        return server_error("Internal Server Error")

    if result.get("status") == "NOT_FOUND":
        return not_found("Salary record not found")

    try:
        _send_notice_safe(
            logger=logger,
            hlog=hlog,
            user_id=user_id,
            notice_type="your_salary_changed",
            data=_build_salary_change_notice_data(
                firm_id=firm_id,
                user_id=user_id,
                firm_name=_read_firm_name(
                    firms_pool=firms_pool,
                    firms_database=firms_database,
                    firm_id=firm_id,
                )
                or f"Фирма {firm_id}",
                salary_snapshot=_read_employee_salary_snapshot(
                    notices_pool=notices_pool,
                    notices_database=notices_database,
                    firm_id=firm_id,
                    user_id=user_id,
                ),
                effective_from=None,
                action_text="Запись зарплаты удалена",
                status_text="deleted",
            ),
        )
    except Exception as e:
        logger.error("payroll_manager.salary_upsert.notice_failed", error=str(e), trace=traceback.format_exc())
        hlog.exception("payroll_manager.salary_upsert.notice_failed", error=str(e))

    return ok(
        {
            "message": "Salary deleted",
            "firm_id": firm_id,
            "salary_id": salary_id,
            "user_id": user_id,
        }
    )
