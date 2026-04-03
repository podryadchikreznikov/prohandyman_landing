import os
import uuid
from typing import Any, Optional

from utils import build_internal_http_event, build_internal_invocation_context, invoke_function, JsonLogger

from sa import get_iam_token

FUNCTION_HOST = "functions.yandexcloud.net"
SERVICE_NAME = "payroll-manager"


def _get_sequence_generator_function_id() -> Optional[str]:
    return (os.environ.get("FUNCTION_ID_SEQUENCE_NUMBER_GENERATOR") or "").strip() or None


def create_event_entity(
    user_id: str,
    event_type: str,
    payload: dict,
    logger: JsonLogger,
    *,
    firm_id: Optional[str] = None,
    schema_version: int = 1,
) -> str:
    fn_id = _get_sequence_generator_function_id()
    if not fn_id:
        raise RuntimeError("FUNCTION_ID_SEQUENCE_NUMBER_GENERATOR is required")

    iam_token = get_iam_token(logger)
    if not iam_token:
        raise RuntimeError("Failed to get IAM token for internal invoke")

    req_hash = str(os.environ.get("SEQUENCE_GENERATOR_REQUEST_SCHEMA_HASH") or "").strip()
    res_hash = str(os.environ.get("SEQUENCE_GENERATOR_RESPONSE_SCHEMA_HASH") or "").strip()
    if not req_hash or not res_hash:
        raise RuntimeError("SEQUENCE_GENERATOR_REQUEST_SCHEMA_HASH/SEQUENCE_GENERATOR_RESPONSE_SCHEMA_HASH is required")

    body: dict[str, Any] = {
        "event_type": event_type,
        "state_json": payload,
        "schema_version": schema_version,
        "user_id": user_id,
    }
    if firm_id:
        body["firm_id"] = firm_id

    internal_context = build_internal_invocation_context(
        service_name=SERVICE_NAME,
        trace_id=str(uuid.uuid4()),
        firm_id=firm_id,
        initiator_user_id=user_id,
    )
    event = build_internal_http_event(
        path="/sequence/generate",
        body=body,
        internal_context=internal_context,
        request_schema_hash=req_hash,
        response_schema_hash=res_hash,
    )

    logger.info("payroll_manager.sequence_generator.invoke", function_id=fn_id, event_type=event_type)

    res = invoke_function(
        target=f"https://{FUNCTION_HOST}/{fn_id}",
        json_payload=event,
        auth_headers={"Authorization": f"Bearer {iam_token}"},
        allow_hosts=(FUNCTION_HOST,),
        timeout_s=60,
        parse_json=True,
    )

    if not res.get("ok"):
        logger.error("payroll_manager.sequence_generator.failed", error=res.get("error"), status_code=res.get("status_code"))
        raise RuntimeError(f"Failed to generate event: {res.get('error')}")

    data = res.get("json") or {}
    event_id = data.get("event_id")
    if not event_id:
        logger.error("payroll_manager.sequence_generator.bad_response", response=data)
        raise RuntimeError("sequence-number-generator returned no event_id")

    logger.info("payroll_manager.sequence_generator.success", event_id=event_id, event_type=event_type)
    return event_id
