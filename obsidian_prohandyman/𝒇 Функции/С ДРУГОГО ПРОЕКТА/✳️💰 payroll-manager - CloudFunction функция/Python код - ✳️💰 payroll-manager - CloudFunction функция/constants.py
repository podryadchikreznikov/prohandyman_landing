# -*- coding: utf-8 -*-
from __future__ import annotations

ACTION_DEFERRED_CREATE = "deferred_create"
ACTION_CASH_CREATE = "cash_create"
ACTION_ACCRUAL_CREATE = "accrual_create"
ACTION_SALARY_UPSERT = "salary_upsert"
ACTION_SALARY_DELETE = "salary_delete"
ACTION_FINE_CREATE = "fine_create"
ACTION_REWARD_CREATE = "reward_create"
ACTION_DISPATCHER_SETTLEMENT_CREATE = "dispatcher_settlement_create"

EVENT_DEFERRED = "deferred"
EVENT_CASH = "cash"
EVENT_ACCRUAL = "accrual"
EVENT_FINE = "fine"
EVENT_REWARD = "reward"
EVENT_DISPATCHER_SETTLEMENT = "dispatcher_settlement"

_ENDPOINT_DEFERRED_CREATE = "/firms/{firm_id}/payroll/deferred/create"
_ENDPOINT_CASH_CREATE = "/firms/{firm_id}/payroll/cash/create"
_ENDPOINT_ACCRUAL_CREATE = "/firms/{firm_id}/payroll/accrual/create"
_ENDPOINT_SALARY_UPSERT = "/firms/{firm_id}/payroll/salary/upsert"
_ENDPOINT_SALARY_DELETE = "/firms/{firm_id}/payroll/salary/delete"
_ENDPOINT_FINE_CREATE = "/firms/{firm_id}/payroll/fines/create"
_ENDPOINT_REWARD_CREATE = "/firms/{firm_id}/payroll/rewards/create"
_ENDPOINT_DISPATCHER_SETTLEMENT_CREATE = "/firms/{firm_id}/payroll/dispatcher-settlement/create"

ALLOWED_ROLE_TYPES = {"owner", "admin", "accountant", "manager", "foreman", "foreman_foreman"}


def endpoint_for_action(action: str) -> str:
    return {
        ACTION_DEFERRED_CREATE: _ENDPOINT_DEFERRED_CREATE,
        ACTION_CASH_CREATE: _ENDPOINT_CASH_CREATE,
        ACTION_ACCRUAL_CREATE: _ENDPOINT_ACCRUAL_CREATE,
        ACTION_SALARY_UPSERT: _ENDPOINT_SALARY_UPSERT,
        ACTION_SALARY_DELETE: _ENDPOINT_SALARY_DELETE,
        ACTION_FINE_CREATE: _ENDPOINT_FINE_CREATE,
        ACTION_REWARD_CREATE: _ENDPOINT_REWARD_CREATE,
        ACTION_DISPATCHER_SETTLEMENT_CREATE: _ENDPOINT_DISPATCHER_SETTLEMENT_CREATE,
    }.get(action, "")
