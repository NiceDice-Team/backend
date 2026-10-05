import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework import status

from products.infrastructure.models import ProductImage
from products.interfaces import views as product_views


pytestmark = [pytest.mark.api, pytest.mark.django_db]


@pytest.mark.bug
@pytest.mark.django_db(transaction=True)
def test_current_photo_create_defect_returns_500_without_product_image(
    api_client, user_factory
):
    api_client.force_authenticate(user=user_factory())
    api_client.raise_request_exception = False

    response = api_client.post(reverse("photo-list"), {}, format="json")

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert not ProductImage.objects.exists()


def image_upload(name="image.png"):
    data = io.BytesIO()
    Image.new("RGB", (20, 20), "red").save(data, format="PNG")
    return SimpleUploadedFile(name, data.getvalue(), content_type="image/png")


@pytest.mark.bug
def test_current_security_defect_allows_anonymous_product_image_upload(
    api_client, product_factory, monkeypatch
):
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


@pytest.mark.bug
def test_current_security_defect_allows_anonymous_product_image_reorder(api_client, product_factory):
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


@pytest.mark.bug
def test_current_security_defect_allows_anonymous_product_image_delete(
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


def test_product_image_upload_rejects_unknown_product_without_processing(api_client, monkeypatch):
    processed = []
    monkeypatch.setattr(
        product_views,
        "process_and_upload_product_image",
        lambda *args: processed.append(args),
    )

    response = api_client.post(
        reverse("product-image-upload", kwargs={"product_id": 999999}),
        {"image": image_upload()},
        format="multipart",
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert processed == []
    assert not ProductImage.objects.exists()


def test_product_image_delete_rejects_unknown_product_or_image(api_client, product_factory):
    product = product_factory()
    image = ProductImage.objects.create(product=product, sort=1)

    missing_product = api_client.delete(
        reverse("product-image-delete", kwargs={"product_id": 999999, "image_id": image.pk})
    )
    missing_image = api_client.delete(
        reverse("product-image-delete", kwargs={"product_id": product.pk, "image_id": 999999})
    )

    assert missing_product.status_code == status.HTTP_404_NOT_FOUND
    assert missing_image.status_code == status.HTTP_404_NOT_FOUND
    assert ProductImage.objects.filter(pk=image.pk).exists()


def test_ambiguous_current_behavior_deletes_image_metadata_when_storage_cleanup_fails(
    api_client, product_factory, monkeypatch
):
    product = product_factory()
    image = ProductImage.objects.create(product=product, sort=1)
    monkeypatch.setattr(
        product_views,
        "delete_product_image_files",
        lambda value: (_ for _ in ()).throw(RuntimeError("storage unavailable")),
    )

    response = api_client.delete(
        reverse("product-image-delete", kwargs={"product_id": product.pk, "image_id": image.pk})
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not ProductImage.objects.filter(pk=image.pk).exists()


def test_product_image_reorder_rejects_unknown_product(api_client):
    response = api_client.patch(
        reverse("product-image-reorder", kwargs={"product_id": 999999}),
        {"images": [{"id": 1, "sort": 2}]},
        format="json",
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_product_image_reorder_rejects_foreign_image_without_changing_it(
    api_client, product_factory
):
    target = product_factory()
    other = product_factory()
    foreign_image = ProductImage.objects.create(product=other, sort=7)

    response = api_client.patch(
        reverse("product-image-reorder", kwargs={"product_id": target.pk}),
        {"images": [{"id": foreign_image.pk, "sort": 1}]},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    foreign_image.refresh_from_db()
    assert foreign_image.sort == 7


@pytest.mark.bug
def test_current_reorder_atomicity_defect_persists_earlier_update_before_later_validation_failure(
    api_client, product_factory
):
    target = product_factory()
    other = product_factory()
    target_image = ProductImage.objects.create(product=target, sort=7)
    foreign_image = ProductImage.objects.create(product=other, sort=9)

    response = api_client.patch(
        reverse("product-image-reorder", kwargs={"product_id": target.pk}),
        {
            "images": [
                {"id": target_image.pk, "sort": 1},
                {"id": foreign_image.pk, "sort": 2},
            ]
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    target_image.refresh_from_db()
    foreign_image.refresh_from_db()
    assert target_image.sort == 1
    assert foreign_image.sort == 9


@pytest.mark.parametrize(
    "payload",
    [{}, {"images": [{"id": 1}]}, {"images": [{"sort": 1}]}],
)
def test_product_image_reorder_rejects_malformed_payload(api_client, product_factory, payload):
    product = product_factory()

    response = api_client.patch(
        reverse("product-image-reorder", kwargs={"product_id": product.pk}),
        payload,
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["errors"][0]["attr"] == "images"


def test_product_image_reorder_currently_accepts_empty_list_as_noop(api_client, product_factory):
    product = product_factory()
    image = ProductImage.objects.create(product=product, sort=7)

    response = api_client.patch(
        reverse("product-image-reorder", kwargs={"product_id": product.pk}),
        {"images": []},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"message": "Порядок зображень успішно оновлено."}
    image.refresh_from_db()
    assert image.sort == 7
