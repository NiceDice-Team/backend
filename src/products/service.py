import io
import os
import logging
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from PIL import Image
from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.db import models

from products.infrastructure.models import Product, ProductImage

logger = logging.getLogger(__name__)


def process_and_upload_product_image(product: Product, image_file, alt_text: str) -> ProductImage:
    original_name = os.path.splitext(image_file.name)[0]
    base_filename = f"{product.id}_{original_name}"
    webp_images = {}

    # Large (1200px)
    with Image.open(image_file) as img:
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")
        img_lg = img.copy()
        img_lg.thumbnail((1200, 1200), Image.LANCZOS)
        buffer_lg = io.BytesIO()
        img_lg.save(buffer_lg, format='WEBP', quality=85, method=6)
        buffer_lg.seek(0)
        webp_images['lg'] = buffer_lg

    # Medium (600px)
    with Image.open(image_file) as img:
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")
        img_md = img.copy()
        img_md.thumbnail((600, 600), Image.LANCZOS)
        buffer_md = io.BytesIO()
        img_md.save(buffer_md, format='WEBP', quality=80, method=6)
        buffer_md.seek(0)
        webp_images['md'] = buffer_md

    # Small (300px)
    with Image.open(image_file) as img:
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")
        img_sm = img.copy()
        img_sm.thumbnail((300, 300), Image.LANCZOS)
        buffer_sm = io.BytesIO()
        img_sm.save(buffer_sm, format='WEBP', quality=75, method=6)
        buffer_sm.seek(0)
        webp_images['sm'] = buffer_sm

    storage = storages['default']

    filenames = {
        'lg': f"products/lg/{base_filename}_lg_{os.urandom(3).hex()}.webp",
        'md': f"products/md/{base_filename}_md_{os.urandom(3).hex()}.webp",
        'sm': f"products/sm/{base_filename}_sm_{os.urandom(3).hex()}.webp",
    }

    urls = {}
    urls['url_lg'] = storage.url(
        storage.save(filenames['lg'], ContentFile(webp_images['lg'].getvalue()))
    )
    urls['url_md'] = storage.url(
        storage.save(filenames['md'], ContentFile(webp_images['md'].getvalue()))
    )
    urls['url_sm'] = storage.url(
        storage.save(filenames['sm'], ContentFile(webp_images['sm'].getvalue()))
    )

    # --- Збереження оригіналу без змін ---
    image_file.seek(0)
    original_extension = os.path.splitext(image_file.name)[1]
    unique_suffix = os.urandom(3).hex()
    original_filename_for_storage = f"products/original/{base_filename}_original_{unique_suffix}{original_extension}"
    original_file_path = storage.save(original_filename_for_storage, image_file)
    url_original = storage.url(original_file_path)

    # --- Створення запису в БД ---
    max_sort_value = product.images.aggregate(models.Max('sort'))['sort__max'] or 0
    new_sort_value = max_sort_value + 1

    product_image = ProductImage.objects.create(
        product=product,
        url_original=url_original,
        url_lg=urls['url_lg'],
        url_md=urls['url_md'],
        url_sm=urls['url_sm'],
        alt=alt_text,
        sort=new_sort_value
    )

    return product_image


def _extract_key_from_url(url: str) -> str:
    """Витягує ключ об'єкта з URL сховища."""
    if not url:
        return ""
    parsed_url = urlparse(url)
    return parsed_url.path.lstrip('/')


def invalidate_cloudfront_cache(paths_to_invalidate: list):

    """Інвалідує кеш CloudFront"""
    logger.info(f"Starting CloudFront invalidation for paths: {paths_to_invalidate}")

    # Отримуємо distribution_id зі змінного середовища
    distribution_id = os.getenv('AWS_CLOUDFRONT_DISTRIBUTION_ID')
    logger.info(f"Using CloudFront Distribution ID: {distribution_id}")
    if not distribution_id:
        logger.warning("AWS_CLOUDFRONT_DISTRIBUTION_ID environment variable not set. Skipping CloudFront invalidation.")
        return

    if not paths_to_invalidate:
        logger.info("No paths provided for CloudFront invalidation.")
        return

    try:
        aws_access_key_id = os.getenv('AWS_S3_ACCESS_KEY_ID')
        aws_secret_access_key = os.getenv('AWS_S3_SECRET_ACCESS_KEY')

        if not aws_access_key_id or not aws_secret_access_key:
            logger.error(
                "AWS credentials (AWS_S3_ACCESS_KEY_ID/AWS_S3_SECRET_ACCESS_KEY) not found in environment variables. Unable to invalidate CloudFront cache.")
            return

        logger.info("Attempting to create CloudFront client with explicit credentials...")
        cloudfront_client = boto3.client(
            'cloudfront',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key
        )
        logger.info("CloudFront client created successfully.")

        logger.info("Attempting to create invalidation...")
        response = cloudfront_client.create_invalidation(
            DistributionId=distribution_id,
            InvalidationBatch={
                'Paths': {
                    'Quantity': len(paths_to_invalidate),
                    'Items': paths_to_invalidate
                },
                'CallerReference': f'invalidation-{os.urandom(16).hex()}'
            }
        )
        logger.info("CloudFront invalidation request sent.")
        invalidation_id = response['Invalidation']['Id']
        logger.info(f"CloudFront invalidation created successfully. Invalidation ID: {invalidation_id}")

    except NoCredentialsError:
        logger.error(
            "AWS credentials not found or invalid (NoCredentialsError). Unable to invalidate CloudFront cache.")
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        logger.error(f"Failed to invalidate CloudFront cache: {error_code} - {error_message}")
        logger.error(f"Full error response: {e.response}")
    except Exception as e:
        logger.error(f"Unexpected error during CloudFront invalidation: {e}", exc_info=True)


def delete_product_image_files(product_image: ProductImage):
    """Видаляє всі файли зображення (оригінал, lg, md, sm) з S3 і інвалідує їх у CloudFront."""
    storage = storages['default']
    file_url_fields = ['url_original', 'url_lg', 'url_md', 'url_sm']

    deleted_keys = []
    paths_to_invalidate = []

    for field_name in file_url_fields:
        url = getattr(product_image, field_name, None)
        if url:
            try:
                key = _extract_key_from_url(url)
                if key:
                    storage.delete(key)
                    deleted_keys.append(key)
                    paths_to_invalidate.append(f"/{key}")
                    logger.info(f"Deleted file from storage: {key} (from {field_name})")
                else:
                    logger.warning(f"Could not extract key from URL: {url} (field: {field_name})")
            except Exception as e:
                logger.error(f"Error deleting file {url} (from {field_name}) from storage: {e}")

    # Інвалідуємо кеш CloudFront для видалених файлів
    if paths_to_invalidate:
        invalidate_cloudfront_cache(paths_to_invalidate)
    else:
        logger.info("No files were deleted, skipping CloudFront invalidation.")
