import os
import ydb

def ydb_creds_from_env():
    sa_key_file = os.environ.get("SA_KEY_FILE")
    if sa_key_file:
        return ydb.iam.ServiceAccountCredentials.from_file(sa_key_file)
    try:
        return ydb.iam.MetadataUrlCredentials()
    except Exception:
        return ydb.iam.MetadataUrlCredentials()
