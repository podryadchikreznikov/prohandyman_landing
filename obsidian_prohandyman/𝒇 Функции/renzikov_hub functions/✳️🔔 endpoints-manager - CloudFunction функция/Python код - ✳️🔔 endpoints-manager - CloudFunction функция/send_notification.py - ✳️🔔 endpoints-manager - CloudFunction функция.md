
```python
# send_notification.py

import os
import json
import hashlib
import datetime
import uuid
import boto3
import ydb
from botocore.exceptions import ClientError
from custom_errors import LogicError
from utils import rustore_push_utils
from utils import JsonLogger, ok, now_utc, loads_safe, get_driver_from_env

def _create_notices_table_if_not_exists(driver, user_id):
    table_path = os.path.join(os.environ["YDB_DATABASE_NOTICES"], f"notices_{user_id}")
    try:
        session = driver.table_client.session().create()
        session.describe_table(table_path)
    except ydb.SchemeError:
        # создаём таблицу при первом уведомлении
        session.create_table(
            table_path,
            ydb.TableDescription().with_primary_key("notice_id")
            .with_columns(
                ydb.Column("notice_id", ydb.PrimitiveType.Utf8),
                ydb.Column("title", ydb.OptionalType(ydb.PrimitiveType.Utf8)),
                ydb.Column("provider", ydb.OptionalType(ydb.PrimitiveType.Utf8)),
                ydb.Column("tags_json", ydb.OptionalType(ydb.PrimitiveType.Json)),
                ydb.Column("additional_info_json", ydb.OptionalType(ydb.PrimitiveType.Json)),
                ydb.Column("action_url", ydb.OptionalType(ydb.PrimitiveType.Utf8)),
                ydb.Column("created_at", ydb.OptionalType(ydb.PrimitiveType.Timestamp)),
                ydb.Column("is_delivered", ydb.OptionalType(ydb.PrimitiveType.Bool)),
                ydb.Column("delivered_at", ydb.OptionalType(ydb.PrimitiveType.Timestamp)),
                ydb.Column("is_archived", ydb.OptionalType(ydb.PrimitiveType.Bool))
            )
        )
        
def handle_send_notification(endpoints_pool, notices_pool, user_id, payload):
    logger = JsonLogger()
    if not all([user_id, payload, payload.get('title'), payload.get('body')]):
        raise LogicError("user_id_to_notify, payload.title and payload.body are required.")

    # ensure table exists (get driver from env)
    notices_driver = get_driver_from_env(endpoint_var="YDB_ENDPOINT_NOTICES", database_var="YDB_DATABASE_NOTICES")
    _create_notices_table_if_not_exists(notices_driver, user_id)
    
    title = payload.get("title")
    body = payload.get("body")

    def create_notice_record(session):
        tx = session.transaction(ydb.SerializableReadWrite())
        table_name = f"notices_{user_id}"
        query = session.prepare(f"""
            DECLARE $id AS Utf8;
            DECLARE $title AS Utf8;
            DECLARE $provider AS Utf8;
            DECLARE $additional_info AS Json;
            DECLARE $created AS Timestamp;
            DECLARE $is_delivered AS Bool;
            
            UPSERT INTO `{table_name}` (notice_id, title, provider, additional_info_json, created_at, is_delivered)
            VALUES ($id, $title, $provider, $additional_info, $created, $is_delivered);
        """)
        
        additional_info_payload = {
            "body": body,
            "source": "internal_trigger",
            "task_id": payload.get("task_id")
        }
        parent_id = payload.get("parent_task_id")
        if parent_id:
            additional_info_payload["parent_task_id"] = parent_id

        tx.execute(query, {
            "$id": str(uuid.uuid4()),
            "$title": title,
            "$provider": "приложение",
            "$additional_info": json.dumps(additional_info_payload),
            "$created": now_utc(),
            "$is_delivered": False
        })
        tx.commit()
    notices_pool.retry_operation_sync(create_notice_record)

    def get_active_subscriptions(session):
        query = session.prepare("""
            DECLARE $uid AS Utf8;
            SELECT push_token, platform, endpoint_arn FROM UserEndpoints VIEW user_id_index
            WHERE user_id = $uid AND is_enabled = true;
        """)
        res = session.transaction(ydb.SerializableReadWrite()).execute(query, {"$uid": user_id}, commit_tx=True)
        return res[0].rows
    
    subscriptions = endpoints_pool.retry_operation_sync(get_active_subscriptions)
    if not subscriptions:
        return ok({"message": "Notification saved, but no active devices found."})

    cns_client = boto3.client(
        'sns',
        region_name=os.environ['CNS_REGION'],
        endpoint_url=os.environ.get('CNS_ENDPOINT_URL', 'https://notifications.yandexcloud.net'),
        aws_access_key_id=os.environ.get('STATIC_ACCESS_KEY_ID'),
        aws_secret_access_key=os.environ.get('STATIC_SECRET_ACCESS_KEY')
    )
    rustore_project_id = os.environ['RUSTORE_PROJECT_ID']
    rustore_service_token = os.environ['RUSTORE_SERVICE_TOKEN']
    
    success_count = 0
    disabled_tokens = []

    for sub in subscriptions:
        is_sent = False
        error_reason = ""
        
        if sub.platform == "WEB" and sub.endpoint_arn:
            web_payload = {"notification": {"title": title, "body": body}}
            message_to_publish = {"default": body, "WEB": json.dumps(web_payload)}
            try:
                cns_client.publish(
                    TargetArn=sub.endpoint_arn,
                    Message=json.dumps(message_to_publish),
                    MessageStructure="json"
                )
                is_sent = True
            except ClientError as e:
                if e.response.get("Error", {}).get("Code") == 'EndpointDisabled':
                    error_reason = "EndpointDisabled"
                logger.error("endpoints.cns_publish_error", arn=sub.endpoint_arn, error=str(e))

        elif sub.platform == "RUSTORE":
            is_sent, error_reason = rustore_push_utils.send_rustore_notification(
                project_id=rustore_project_id, service_token=rustore_service_token,
                device_token=sub.push_token, title=title, body=body
            )

        if is_sent:
            success_count += 1
        elif error_reason in ["EndpointDisabled", "UNREGISTERED"]:
            disabled_tokens.append(sub.push_token)
            logger.warn("endpoints.mark_token_disabled", tail=sub.push_token[-10:], reason=error_reason)

    if disabled_tokens:
        logger.info("endpoints.deactivate_disabled", count=len(disabled_tokens))
        disabled_hashes = [hashlib.sha256(t.encode('utf-8')).hexdigest() for t in disabled_tokens]
        
        def disable_subscriptions_batch(session):
            query = session.prepare("""
                DECLARE $hashes AS List<Utf8>;
                UPDATE UserEndpoints SET is_enabled = false, updated_at = CurrentUtcTimestamp()
                WHERE push_token_hash IN $hashes;
            """)
            session.transaction(ydb.SerializableReadWrite()).execute(
                query, {"$hashes": disabled_hashes}, commit_tx=True
            )
        try:
            endpoints_pool.retry_operation_sync(disable_subscriptions_batch)
            logger.info("endpoints.deactivate_ok")
        except Exception as db_error:
            logger.error("endpoints.deactivate_failed", error=str(db_error))

    message = f"Notification sent to {success_count} of {len(subscriptions)} devices."
    logger.info("endpoints.send_result", message=message)
    return ok({"message": message})
```