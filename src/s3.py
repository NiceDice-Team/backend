import os
import boto3
from storages.backends.s3boto3 import S3Boto3Storage


class MediaStorage(S3Boto3Storage):
    def __init__(self, *args, **kwargs):
        kwargs["bucket_name"] = 'bg-shop-images'
        kwargs["custom_domain"] = 'cdn.bgshop.work.gd'
        kwargs["file_overwrite"] = False
        kwargs["querystring_auth"] = False

        session = boto3.session.Session(
            aws_access_key_id=os.getenv("AWS_S3_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_S3_SECRET_ACCESS_KEY"),
            region_name=os.getenv('AWS_S3_REGION_NAME', 'eu-north-1'),
        )

        super().__init__(*args, **kwargs)

        self.session = session
