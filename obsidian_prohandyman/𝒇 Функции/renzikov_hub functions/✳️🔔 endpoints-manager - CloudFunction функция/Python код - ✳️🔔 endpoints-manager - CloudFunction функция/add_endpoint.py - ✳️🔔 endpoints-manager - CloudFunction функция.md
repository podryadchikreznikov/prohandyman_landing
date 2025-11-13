```python
# add_endpoint.py

import os
import json
import hashlib
import boto3
import ydb
from botocore.exceptions import ClientError
from custom_errors import LogicError
from utils import JsonLogger, created, now_utc

def _detect_platform(token):
    """Определяет платформу по формату токена."""
    try:
        data = json.loads(token)
        if isinstance(data, dict) and 'endpoint' in data and 'keys' in data:
            return "WEB"
    except (json.JSONDecodeError, TypeError):
        pass
    return "RUSTORE"

def handle_add_endpoint(pool, user_id, push_token, device_info):
    logger = JsonLogger()
    if not push_token:
        raise LogicError("push_token is required.")

    platform = _detect_platform(push_token)
    token_hash = hashlib.sha256(push_token.encode('utf-8')).hexdigest()
    endpoint_arn = None

    if platform == "WEB":
        cns_client = boto3.client(
            'sns',
            region_name=os.environ['CNS_REGION'],
            endpoint_url=os.environ.get('CNS_ENDPOINT_URL', 'https://notifications.yandexcloud.net'),
            aws_access_key_id=os.environ.get('STATIC_ACCESS_KEY_ID'),
            aws_secret_access_key=os.environ.get('STATIC_SECRET_ACCESS_KEY')
        )
        try:
            response = cns_client.create_platform_endpoint(
                PlatformApplicationArn=os.environ['CNS_PLATFORM_APP_ARN_WEB'],
                Token=push_token
            )
            endpoint_arn = response['EndpointArn']
        except ClientError as e:
            if 'Endpoint already exists' in str(e):
                endpoint_arn = str(e).split(' ')[-1]
                logger.warn("endpoints.web_exists_enable", arn=endpoint_arn)
                cns_client.set_endpoint_attributes(EndpointArn=endpoint_arn, Attributes={'Enabled': 'true'})
            else:
                raise LogicError(f"Could not create WEB push endpoint: {e}")

    def upsert_db_record(session):
        query = session.prepare("""
            DECLARE $hash AS Utf8; DECLARE $uid AS Utf8; DECLARE $platform AS Utf8;
            DECLARE $token AS Utf8; DECLARE $arn AS Utf8?; DECLARE $enabled AS Bool; 
            DECLARE $device AS Json; DECLARE $now AS Timestamp;
            UPSERT INTO UserEndpoints (push_token_hash, user_id, platform, push_token, endpoint_arn, is_enabled, device_info_json, created_at, updated_at)
            VALUES ($hash, $uid, $platform, $token, $arn, $enabled, $device, $now, $now);
        """)
        session.transaction(ydb.SerializableReadWrite()).execute(query, {
            "$hash": token_hash, "$uid": user_id, "$platform": platform, "$token": push_token,
            "$arn": endpoint_arn, "$enabled": True, "$device": json.dumps(device_info),
            "$now": now_utc()
        }, commit_tx=True)

    pool.retry_operation_sync(upsert_db_record)
    logger.info("endpoints.upsert_ok", platform=platform, user_id=user_id)
    return created({"message": "Endpoint processed successfully"})
```