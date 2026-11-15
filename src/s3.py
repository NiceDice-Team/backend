import os
import boto3
from storages.backends.s3boto3 import S3Boto3Storage


class MediaStorage(S3Boto3Storage):
    def __init__(self, *args, **kwargs):
        kwargs["bucket_name"] = 'bg-shop-images'
        kwargs["custom_domain"] = 'cdn.bgshop.work.gd'
        kwargs["file_overwrite"] = False
        kwargs["querystring_auth"] = False

        access_key = os.getenv("AWS_S3_ACCESS_KEY_ID")
        secret_key = os.getenv("AWS_S3_SECRET_ACCESS_KEY")
        endpoint_url = os.getenv("AWS_S3_ENDPOINT_URL")
        region_name = os.getenv("AWS_S3_REGION_NAME", "eu-north-1")

        if access_key:
            kwargs["access_key"] = access_key
        if secret_key:
            kwargs["secret_key"] = secret_key
        if endpoint_url:
            kwargs["endpoint_url"] = endpoint_url
        if region_name:
            kwargs["region_name"] = region_name

        session = boto3.session.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region_name,
        )

        super().__init__(*args, **kwargs)
        self.session = session
