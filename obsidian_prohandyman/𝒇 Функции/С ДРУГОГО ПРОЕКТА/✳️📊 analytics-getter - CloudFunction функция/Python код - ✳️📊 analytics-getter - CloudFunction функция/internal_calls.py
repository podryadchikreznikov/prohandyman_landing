# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import time
import uuid
from typing import Dict

from utils import JsonLogger, build_internal_http_event, build_internal_invocation_context
from utils.util_invoke.invoke import invoke_function
from utils.util_log import YCLogger

from sa import get_iam_token

FUNCTION_HOST = "functions.yandexcloud.net"
SERVICE_NAME = "analytics-getter"


def call_vector_search_manager_search_objects(
    *,
    initiator_user_id: str,
    initiator_role_type: str | None,
    firm_id: str,
    query: str,
    page: int,
    page_size: int,
    logger: JsonLogger,
    hlog: YCLogger | None = None,
) -> Dict[str, Any]:
    fn_id = os.environ.get("FN_VECTOR_SEARCH_MANAGER")
    if not fn_id:
        raise RuntimeError("FN_VECTOR_SEARCH_MANAGER is not configured")

    req_hash = os.environ.get("VECTOR_SEARCH_MANAGER_SEARCH_REQUEST_SCHEMA_HASH")
    res_hash = os.environ.get("VECTOR_SEARCH_MANAGER_SEARCH_RESPONSE_SCHEMA_HASH")
    if not req_hash or not res_hash:
        raise RuntimeError(
            "VECTOR_SEARCH_MANAGER_SEARCH_REQUEST_SCHEMA_HASH/"
            "VECTOR_SEARCH_MANAGER_SEARCH_RESPONSE_SCHEMA_HASH is required"
        )

    iam_token = get_iam_token(logger)
    if not iam_token:
        raise RuntimeError("Failed to get IAM token for vector-search-manager invoke")

    payload = {
        "action": "search",
        "source_table": "firm_objects",
        "firm_id": firm_id,
        "category": "main",
        "query": query,
        "page": int(page) + 1,
        "page_size": int(page_size),
        "include_entity": False,
    }

    if hlog:
        hlog.hard(
            "→invoke.vector_search_manager.search_objects",
            fn_id=fn_id,
            firm_id=firm_id,
            page=int(page),
            page_size=int(page_size),
            payload_preview=YCLogger.preview(payload, 2500),
        )

    internal_context = build_internal_invocation_context(
        service_name=SERVICE_NAME,
        trace_id=str(uuid.uuid4()),
        firm_id=firm_id,
        initiator_user_id=initiator_user_id,
        initiator_role_type=initiator_role_type,
        source_type="firm_objects",
        source_id=query,
    )
    event = build_internal_http_event(
        path=f"/firms/{firm_id}/vector/search/objects",
        body=payload,
        internal_context=internal_context,
        request_schema_hash=req_hash,
        response_schema_hash=res_hash,
        action="search",
    )

    t0 = time.time()
    resp = invoke_function(
        target=f"https://{FUNCTION_HOST}/{fn_id}",
        json_payload=event,
        auth_headers={"Authorization": f"Bearer {iam_token}"},
        allow_hosts=(FUNCTION_HOST,),
        parse_json=True,
        timeout_s=60,
    )
    elapsed_ms = int((time.time() - t0) * 1000)

    if not resp.get("ok"):
        status_code = resp.get("status_code")
        body_preview = (resp.get("body_text") or "")[:500]
        logger.error(
            "analytics_getter.vector_search_manager.search_failed",
            meta=resp.get("meta"),
            status_code=status_code,
            body_preview=body_preview,
        )
        if hlog:
            hlog.error(
                "invoke.vector_search_manager.search_failed",
                fn_id=fn_id,
                status_code=status_code,
                elapsed_ms=elapsed_ms,
                meta_preview=YCLogger.preview(resp.get("meta"), 2500),
                body_preview=body_preview,
            )
        raise RuntimeError("vector-search-manager search failed")

    out = resp.get("json") or {}
    if hlog:
        hlog.hard(
            "invoke.vector_search_manager.search_ok",
            fn_id=fn_id,
            status_code=resp.get("status_code"),
            elapsed_ms=elapsed_ms,
            items_count=len(out.get("items") or []) if isinstance(out, dict) else None,
        )
    return out
