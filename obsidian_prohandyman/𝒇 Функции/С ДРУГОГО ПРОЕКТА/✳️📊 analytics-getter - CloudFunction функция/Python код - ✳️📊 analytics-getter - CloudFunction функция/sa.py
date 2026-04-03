# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import time
import traceback
from datetime import datetime, timezone
from typing import Any, Optional, Tuple

from utils import JsonLogger
from utils.util_yc_sa import get_sa_key_dict_from_lockbox
from utils.util_yc_sa.loader import YcSaLoader


_IAM_TOKEN_CACHE = {"token": None, "expires_at": 0}
_SA_KEY_CACHE: Optional[dict] = None
_CREDENTIALS_CACHE = None


def _load_sa_key_dict(logger: JsonLogger) -> dict:
    global _SA_KEY_CACHE
    if _SA_KEY_CACHE is not None:
        return _SA_KEY_CACHE

    secret_id = os.environ.get("SA_AUTHKEY_LOCKBOX_SECRET_NAME")
    if not secret_id:
        logger.error("analytics_getter.config.missing_env", var="SA_AUTHKEY_LOCKBOX_SECRET_NAME")
        raise RuntimeError("SA_AUTHKEY_LOCKBOX_SECRET_NAME is required")

    _SA_KEY_CACHE = get_sa_key_dict_from_lockbox(secret_id)
    return _SA_KEY_CACHE


def get_ydb_credentials(logger: JsonLogger):
    global _CREDENTIALS_CACHE
    if _CREDENTIALS_CACHE is not None:
        return _CREDENTIALS_CACHE

    try:
        sa_key_dict = _load_sa_key_dict(logger)
        _CREDENTIALS_CACHE = YcSaLoader.make_ydb_credentials_from_sa_key_dict(sa_key_dict)
        return _CREDENTIALS_CACHE
    except Exception as e:
        msg = str(e)
        if "169.254.169.254" in msg or "computeMetadata" in msg:
            logger.error(
                "analytics_getter.lockbox_bootstrap_sa_missing",
                error=msg,
                hint="Cloud Function must have a service account attached to access Lockbox via SDK() metadata token.",
            )
        else:
            logger.error("analytics_getter.lockbox_failed", error=msg, trace=traceback.format_exc())
        raise


def _parse_token_value(token_value: Any, *, now_ts: float) -> Tuple[Optional[str], Optional[float]]:
    if isinstance(token_value, (tuple, list)):
        if len(token_value) >= 2:
            token = token_value[0]
            expires_at = token_value[1]
        elif len(token_value) == 1:
            token = token_value[0]
            expires_at = None
        else:
            return None, None

        if isinstance(expires_at, datetime):
            expires_at_ts = expires_at.timestamp()
        elif isinstance(expires_at, (int, float)):
            expires_at_ts = float(expires_at)
        else:
            expires_at_ts = None

        return (token.decode("utf-8") if isinstance(token, (bytes, bytearray)) else str(token)), expires_at_ts

    if isinstance(token_value, dict):
        token = token_value.get("access_token") or token_value.get("token") or token_value.get("iam_token")
        expires_at = token_value.get("expires_at") or token_value.get("expiration_time") or token_value.get("expires")
        if isinstance(expires_at, datetime):
            expires_at_ts = expires_at.timestamp()
        elif isinstance(expires_at, (int, float)):
            expires_at_ts = float(expires_at)
        else:
            expires_at_ts = None
        return (token.decode("utf-8") if isinstance(token, (bytes, bytearray)) else str(token)) if token else None, expires_at_ts

    if isinstance(token_value, (bytes, bytearray)):
        return token_value.decode("utf-8"), None

    if isinstance(token_value, str):
        return token_value, None

    return None, None


def get_iam_token(logger: JsonLogger) -> Optional[str]:
    global _IAM_TOKEN_CACHE
    now_ts = time.time()
    if _IAM_TOKEN_CACHE["token"] and now_ts < _IAM_TOKEN_CACHE["expires_at"]:
        return _IAM_TOKEN_CACHE["token"]

    try:
        creds = get_ydb_credentials(logger)
        token_value = getattr(creds, "token", None)

        token, expires_at_ts = _parse_token_value(token_value, now_ts=now_ts)
        if not token:
            logger.error("analytics_getter.iam_token.failed", error="Token value is empty")
            return None

        if not expires_at_ts:
            expires_at_ts = now_ts + 1800

        _IAM_TOKEN_CACHE["token"] = token
        _IAM_TOKEN_CACHE["expires_at"] = expires_at_ts - 60
        logger.info("analytics_getter.iam_token.refreshed", expires_in_sec=int(expires_at_ts - now_ts))
        return token
    except Exception as e:
        msg = str(e)
        if "169.254.169.254" in msg or "computeMetadata" in msg:
            logger.error(
                "analytics_getter.iam_token.bootstrap_sa_missing",
                error=msg,
                hint="Cloud Function must have a service account attached to access Lockbox via SDK() metadata token.",
            )
        else:
            logger.error("analytics_getter.iam_token.failed", error=msg, trace=traceback.format_exc())
        return None