
```python
# delete_endpoint.py

import os
import json
import hashlib
import boto3
import ydb
from botocore.exceptions import ClientError
from custom_errors import LogicError, AuthError, NotFoundError
from utils import JsonLogger, ok

def handle_delete_endpoint(pool, push_token, requesting_user_id):
    logger = JsonLogger()
    if not push_token:
        raise LogicError("push_token is required to delete an endpoint.")

    token_hash = hashlib.sha256(push_token.encode('utf-8')).hexdigest()

    def get_subscription_details(session):
        query = session.prepare("DECLARE $hash AS Utf8; SELECT user_id, platform, endpoint_arn FROM UserEndpoints WHERE push_token_hash = $hash;")
        res = session.transaction(ydb.SerializableReadWrite()).execute(query, {"$hash": token_hash}, commit_tx=True)
        if not res[0].rows:
            return None
        return res[0].rows[0]

    sub_details = pool.retry_operation_sync(get_subscription_details)

    if not sub_details:
        raise NotFoundError("Subscription with the provided token not found.")

    if sub_details.user_id != requesting_user_id:
        raise AuthError("You are not authorized to delete this subscription.")

    if sub_details.platform == "WEB" and sub_details.endpoint_arn:
        try:
            cns_client = boto3.client(
                'sns',
                region_name=os.environ['CNS_REGION'],
                endpoint_url=os.environ.get('CNS_ENDPOINT_URL', 'https://notifications.yandexcloud.net'),
                aws_access_key_id=os.environ.get('STATIC_ACCESS_KEY_ID'),
                aws_secret_access_key=os.environ.get('STATIC_SECRET_ACCESS_KEY')
            )
            cns_client.delete_endpoint(EndpointArn=sub_details.endpoint_arn)
            logger.info("endpoints.cns_delete_ok", arn=sub_details.endpoint_arn)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == 'NotFound':
                logger.warn("endpoints.cns_already_deleted", arn=sub_details.endpoint_arn)
            else:
                logger.error("endpoints.cns_delete_error", arn=sub_details.endpoint_arn, error=str(e))

    def delete_from_db(session):
        query = session.prepare("DECLARE $hash AS Utf8; DELETE FROM UserEndpoints WHERE push_token_hash = $hash;")
        session.transaction(ydb.SerializableReadWrite()).execute(query, {"$hash": token_hash}, commit_tx=True)

    pool.retry_operation_sync(delete_from_db)
    logger.info("endpoints.db_delete_ok", token_hash=token_hash)
    return ok({"message": "Subscription deleted successfully."})
```