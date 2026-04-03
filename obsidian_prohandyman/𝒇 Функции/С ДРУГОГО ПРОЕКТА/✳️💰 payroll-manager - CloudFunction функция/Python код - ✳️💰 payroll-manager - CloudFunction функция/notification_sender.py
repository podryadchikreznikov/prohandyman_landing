from __future__ import annotations

import json
import os
import traceback
from typing import Any, Optional

import boto3

from utils import JsonLogger
from utils.util_log import YCLogger
from utils.util_yc_sa.loader import YcSaLoader


_SQS_CLIENT_CACHE: dict[str, Any] = {}


def _get_ymq_credentials() -> tuple[str, str]:
    secret_id = (os.environ.get("YMQ_LOCKBOX_SECRET_ID") or "").strip()
    if not secret_id:
        raise RuntimeError("YMQ_LOCKBOX_SECRET_ID is required")

    loader = YcSaLoader()
    payload = loader._read_lockbox_payload(secret_id=secret_id, version_id=None)

    access_key_id = None
    secret_access_key = None
    if isinstance(payload, dict):
        access_key_id = payload.get("access_key_id") or payload.get("aws_access_key_id")
        secret_access_key = payload.get("secret_access_key") or payload.get("aws_secret_access_key")
    else:
        for entry in getattr(payload, "entries", []) or []:
            key = getattr(entry, "key", "")
            value = getattr(entry, "text_value", None) or getattr(entry, "textValue", None)
            if key in ("access_key_id", "aws_access_key_id"):
                access_key_id = value
            elif key in ("secret_access_key", "aws_secret_access_key"):
                secret_access_key = value

    if not access_key_id or not secret_access_key:
        raise RuntimeError("Lockbox secret must contain access_key_id and secret_access_key")

    return str(access_key_id), str(secret_access_key)


def _get_sqs_client() -> Any:
    cached = _SQS_CLIENT_CACHE.get("client")
    if cached is not None:
        return cached

    folder_id = (os.environ.get("YMQ_FOLDER_ID") or "").strip()
    if not folder_id:
        raise RuntimeError("YMQ_FOLDER_ID is required")

    access_key_id, secret_access_key = _get_ymq_credentials()
    client = boto3.client(
        "sqs",
        region_name="ru-central1",
        endpoint_url="https://message-queue.api.cloud.yandex.net",
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
        aws_session_token=folder_id,
    )
    _SQS_CLIENT_CACHE["client"] = client
    return client


def send_notification(
    *,
    logger: JsonLogger,
    hlog: YCLogger,
    user_id_to_notify: str,
    notice_type: str,
    data: dict[str, Any],
    action_url: Optional[str] = None,
) -> Optional[dict]:
    queue_url = (os.environ.get("YMQ_QUEUE_URL") or "").strip()
    if not queue_url:
        logger.error("payroll_manager.notification_sender.queue_url_missing")
        hlog.hard("notification_sender.queue_url_missing")
        return None

    payload: dict[str, Any] = {
        "user_id_to_notify": user_id_to_notify,
        "payload": {
            "notice_type": notice_type,
            "data": data,
        },
        "meta": {
            "source": "payroll-manager",
        },
    }
    if action_url:
        payload["payload"]["action_url"] = action_url

    try:
        client = _get_sqs_client()
        response = client.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(payload, ensure_ascii=False),
        )
        return {
            "status": 200,
            "message_id": response.get("MessageId"),
        }
    except Exception as e:
        logger.error(
            "payroll_manager.notification_sender.exception",
            notice_type=notice_type,
            user_id=user_id_to_notify,
            error=str(e),
            trace=traceback.format_exc(),
        )
        hlog.exception(
            "notification_sender.exception",
            notice_type=notice_type,
            user_id=user_id_to_notify,
            error=str(e),
        )
        return None