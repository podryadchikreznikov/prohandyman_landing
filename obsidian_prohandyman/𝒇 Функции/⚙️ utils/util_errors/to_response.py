# util_errors/to_response.py
from typing import Dict, Any
from .exceptions import AppError
from ..util_http.response import json_response

def app_error_to_http(err: AppError) -> Dict[str, Any]:
    return json_response(err.http_status, {"error": {"code": err.code, "message": err.message, "details": err.details}})