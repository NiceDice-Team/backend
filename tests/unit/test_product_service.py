import io
from types import SimpleNamespace

import pytest
from botocore.exceptions import ClientError, NoCredentialsError
from PIL import Image

from products import service


pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("", ""),
        (None, ""),
        ("https://cdn.example.com/products/lg/dice.webp", "products/lg/dice.webp"),
        ("https://cdn.example.com/products/dice.webp?version=2#preview", "products/dice.webp"),
        ("/products/original/dice.png", "products/original/dice.png"),
        ("products/original/dice.png", "products/original/dice.png"),
        ("https://cdn.example.com/", ""),
    ],
)
def test_extract_key_from_url(url, expected):
    assert service._extract_key_from_url(url) == expected


def test_cloudfront_invalidation_is_disabled_without_distribution(monkeypatch):
    monkeypatch.delenv("AWS_CLOUDFRONT_DISTRIBUTION_ID", raising=False)
    monkeypatch.setattr(
        service.boto3,
        "client",
        lambda *args, **kwargs: pytest.fail("CloudFront client must not be created"),
    )

    assert service.invalidate_cloudfront_cache(["/products/dice.webp"]) is None


def test_cloudfront_invalidation_requires_paths(monkeypatch):
    monkeypatch.setenv("AWS_CLOUDFRONT_DISTRIBUTION_ID", "distribution-1")
    monkeypatch.setattr(
        service.boto3,
        "client",
        lambda *args, **kwargs: pytest.fail("CloudFront client must not be created"),
    )

    assert service.invalidate_cloudfront_cache([]) is None


def test_cloudfront_invalidation_requires_explicit_credentials(monkeypatch):
    monkeypatch.setenv("AWS_CLOUDFRONT_DISTRIBUTION_ID", "distribution-1")
    monkeypatch.delenv("AWS_S3_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_S3_SECRET_ACCESS_KEY", raising=False)
    monkeypatch.setattr(
        service.boto3,
        "client",
        lambda *args, **kwargs: pytest.fail("CloudFront client must not be created"),
    )

    assert service.invalidate_cloudfront_cache(["/products/dice.webp"]) is None


def test_cloudfront_invalidation_builds_expected_request(monkeypatch):
    monkeypatch.setenv("AWS_CLOUDFRONT_DISTRIBUTION_ID", "distribution-1")
    monkeypatch.setenv("AWS_S3_ACCESS_KEY_ID", "test-access-key")
    monkeypatch.setenv("AWS_S3_SECRET_ACCESS_KEY", "test-secret-key")
    monkeypatch.setattr(service.os, "urandom", lambda size: b"x" * size)
    calls = []

    class FakeCloudFront:
        def create_invalidation(self, **kwargs):
            calls.append(kwargs)
            return {"Invalidation": {"Id": "invalidation-1"}}

    def fake_client(name, **kwargs):
        assert name == "cloudfront"
        assert kwargs == {
            "aws_access_key_id": "test-access-key",
            "aws_secret_access_key": "test-secret-key",
        }
        return FakeCloudFront()

    monkeypatch.setattr(service.boto3, "client", fake_client)

    service.invalidate_cloudfront_cache(["/products/a.webp", "/products/b.webp"])

    assert calls == [
        {
            "DistributionId": "distribution-1",
            "InvalidationBatch": {
                "Paths": {
                    "Quantity": 2,
                    "Items": ["/products/a.webp", "/products/b.webp"],
                },
                "CallerReference": f"invalidation-{(b'x' * 16).hex()}",
            },
        }
    ]


@pytest.mark.parametrize(
    "error",
    [
        NoCredentialsError(),
        ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "denied"}},
            "CreateInvalidation",
        ),
        RuntimeError("unexpected"),
    ],
)
def test_cloudfront_invalidation_contains_client_errors(monkeypatch, error):
    monkeypatch.setenv("AWS_CLOUDFRONT_DISTRIBUTION_ID", "distribution-1")
    monkeypatch.setenv("AWS_S3_ACCESS_KEY_ID", "test-access-key")
    monkeypatch.setenv("AWS_S3_SECRET_ACCESS_KEY", "test-secret-key")

    def fail_client(*args, **kwargs):
        raise error

    monkeypatch.setattr(service.boto3, "client", fail_client)

    assert service.invalidate_cloudfront_cache(["/products/dice.webp"]) is None


def test_delete_product_image_files_deletes_keys_and_invalidates(monkeypatch):
    deleted = []
    invalidated = []
    storage = SimpleNamespace(delete=deleted.append)
    monkeypatch.setattr(service, "storages", {"default": storage})
    monkeypatch.setattr(service, "invalidate_cloudfront_cache", invalidated.append)
    product_image = SimpleNamespace(
        url_original="https://cdn.example.com/products/original/dice.png",
        url_lg="https://cdn.example.com/products/lg/dice.webp?version=2",
        url_md="",
        url_sm=None,
    )

    service.delete_product_image_files(product_image)

    assert deleted == ["products/original/dice.png", "products/lg/dice.webp"]
    assert invalidated == [["/products/original/dice.png", "/products/lg/dice.webp"]]


def test_delete_product_image_files_continues_after_partial_failure(monkeypatch):
    deleted = []
    invalidated = []

    def delete(key):
        if key.endswith("original.png"):
            raise RuntimeError("storage unavailable")
        deleted.append(key)

    monkeypatch.setattr(service, "storages", {"default": SimpleNamespace(delete=delete)})
    monkeypatch.setattr(service, "invalidate_cloudfront_cache", invalidated.append)
    product_image = SimpleNamespace(
        url_original="https://cdn.example.com/products/original/original.png",
        url_lg="https://cdn.example.com/products/lg/dice.webp",
        url_md="https://cdn.example.com/products/md/dice.webp",
        url_sm="",
    )

    service.delete_product_image_files(product_image)

    assert deleted == ["products/lg/dice.webp", "products/md/dice.webp"]
    assert invalidated == [["/products/lg/dice.webp", "/products/md/dice.webp"]]


def test_delete_product_image_files_skips_invalidation_without_deleted_keys(monkeypatch):
    monkeypatch.setattr(
        service,
        "storages",
        {"default": SimpleNamespace(delete=lambda key: pytest.fail("delete must not run"))},
    )
    monkeypatch.setattr(
        service,
        "invalidate_cloudfront_cache",
        lambda paths: pytest.fail("invalidation must not run"),
    )
    product_image = SimpleNamespace(url_original="", url_lg=None, url_md="", url_sm=None)

    assert service.delete_product_image_files(product_image) is None


def test_process_and_upload_product_image_transforms_and_persists_metadata(monkeypatch):
    source = io.BytesIO()
    Image.new("RGBA", (1600, 900), (255, 0, 0, 128)).save(source, format="PNG")
    source.seek(0)
    source.name = "hero.image.png"

    saved = []

    class FakeStorage:
        def save(self, name, content):
            saved.append((name, content.read()))
            return name

        def url(self, name):
            return f"https://cdn.example.com/{name}"

    created = []
    product = SimpleNamespace(
        id=42,
        images=SimpleNamespace(aggregate=lambda *args, **kwargs: {"sort__max": 4}),
    )
    monkeypatch.setattr(service, "storages", {"default": FakeStorage()})
    monkeypatch.setattr(service.os, "urandom", lambda size: b"a" * size)
    monkeypatch.setattr(
        service.ProductImage.objects,
        "create",
        lambda **kwargs: created.append(kwargs) or SimpleNamespace(**kwargs),
    )

    result = service.process_and_upload_product_image(product, source, "Hero image")

    assert [name for name, _ in saved] == [
        "products/lg/42_hero.image_lg_616161.webp",
        "products/md/42_hero.image_md_616161.webp",
        "products/sm/42_hero.image_sm_616161.webp",
        "products/original/42_hero.image_original_616161.png",
    ]
    transformed = [Image.open(io.BytesIO(data)) for _, data in saved[:3]]
    assert [image.size for image in transformed] == [(1200, 675), (600, 338), (300, 169)]
    assert all(image.format == "WEBP" and image.mode == "RGB" for image in transformed)
    assert Image.open(io.BytesIO(saved[3][1])).format == "PNG"
    assert created == [
        {
            "product": product,
            "url_original": "https://cdn.example.com/products/original/42_hero.image_original_616161.png",
            "url_lg": "https://cdn.example.com/products/lg/42_hero.image_lg_616161.webp",
            "url_md": "https://cdn.example.com/products/md/42_hero.image_md_616161.webp",
            "url_sm": "https://cdn.example.com/products/sm/42_hero.image_sm_616161.webp",
            "alt": "Hero image",
            "sort": 5,
        }
    ]
    assert result.sort == 5


def test_process_and_upload_product_image_propagates_storage_failure(monkeypatch):
    source = io.BytesIO()
    Image.new("RGB", (10, 10), "blue").save(source, format="PNG")
    source.seek(0)
    source.name = "dice.png"

    class FailingStorage:
        def url(self, name):
            return f"https://cdn.example.com/{name}"

        def save(self, name, content):
            raise RuntimeError("storage unavailable")

    monkeypatch.setattr(service, "storages", {"default": FailingStorage()})
    product = SimpleNamespace(id=1)

    with pytest.raises(RuntimeError, match="storage unavailable"):
        service.process_and_upload_product_image(product, source, "Dice")
