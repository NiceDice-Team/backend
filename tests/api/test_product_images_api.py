import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework import status

from products.infrastructure.models import ProductImage
from products.interfaces import views as product_views


pytestmark = [pytest.mark.api, pytest.mark.django_db]


def image_upload(name="image.png"):
    data = io.BytesIO()
    Image.new("RGB", (20, 20), "red").save(data, format="PNG")
    return SimpleUploadedFile(name, data.getvalue(), content_type="image/png")


def test_product_image_upload_persists_returned_metadata(api_client, product_factory, monkeypatch):
    product = product_factory()

    def fake_process(target, image, alt):
        assert target == product
        assert image.name == "image.png"
        assert alt == "Box art"
        return ProductImage.objects.create(
            product=product,
            url_original="https://cdn.example.com/original.png",
            url_lg="https://cdn.example.com/lg.webp",
            url_md="https://cdn.example.com/md.webp",
            url_sm="https://cdn.example.com/sm.webp",
            alt=alt,
            sort=1,
        )

    monkeypatch.setattr(product_views, "process_and_upload_product_image", fake_process)

    response = api_client.post(
        reverse("product-image-upload", kwargs={"product_id": product.pk}),
        {"image": image_upload(), "alt": "  Box art  "},
        format="multipart",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["alt"] == "Box art"
    assert ProductImage.objects.get().url_lg == "https://cdn.example.com/lg.webp"


def test_product_image_upload_rejects_missing_or_invalid_file(api_client, product_factory):
    product = product_factory()
    url = reverse("product-image-upload", kwargs={"product_id": product.pk})

    missing = api_client.post(url, {"alt": "No image"}, format="multipart")
    invalid = api_client.post(
        url,
        {"image": SimpleUploadedFile("not-image.txt", b"not image", content_type="text/plain")},
        format="multipart",
    )

    assert missing.status_code == status.HTTP_400_BAD_REQUEST
    assert invalid.status_code == status.HTTP_400_BAD_REQUEST
    assert not ProductImage.objects.exists()


def test_product_image_upload_maps_storage_failure_to_500(api_client, product_factory, monkeypatch):
    product = product_factory()
    monkeypatch.setattr(
        product_views,
        "process_and_upload_product_image",
        lambda *args: (_ for _ in ()).throw(RuntimeError("storage unavailable")),
    )

    response = api_client.post(
        reverse("product-image-upload", kwargs={"product_id": product.pk}),
        {"image": image_upload()},
        format="multipart",
    )

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "storage unavailable" in response.json()["error"]


def test_product_image_reorder_updates_multiple_images(api_client, product_factory):
    product = product_factory()
    first = ProductImage.objects.create(product=product, sort=1)
    second = ProductImage.objects.create(product=product, sort=2)

    response = api_client.patch(
        reverse("product-image-reorder", kwargs={"product_id": product.pk}),
        {"images": [{"id": first.id, "sort": 20}, {"id": second.id, "sort": 10}]},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    first.refresh_from_db()
    second.refresh_from_db()
    assert (first.sort, second.sort) == (20, 10)


def test_product_image_delete_invokes_storage_cleanup_and_removes_metadata(
    api_client, product_factory, monkeypatch
):
    product = product_factory()
    image = ProductImage.objects.create(product=product, sort=1)
    cleaned_ids = []
    monkeypatch.setattr(product_views, "delete_product_image_files", lambda value: cleaned_ids.append(value.pk))

    response = api_client.delete(
        reverse("product-image-delete", kwargs={"product_id": product.pk, "image_id": image.pk})
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert cleaned_ids == [image.pk]
    assert not ProductImage.objects.exists()
