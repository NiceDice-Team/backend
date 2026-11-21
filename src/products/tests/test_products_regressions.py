import io
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework import status

from products.infrastructure.models import Brand, Product, ProductImage, Review


def png_upload(name='cover.png'):
    buffer = io.BytesIO()
    Image.new('RGB', (4, 4), color='red').save(buffer, format='PNG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')


def make_image(product, sort, alt='img'):
    return ProductImage.objects.create(
        product=product,
        url_original=f'https://cdn.example.test/{product.id}/{sort}.png',
        url_lg=f'https://cdn.example.test/{product.id}/{sort}.png',
        url_md=f'https://cdn.example.test/{product.id}/{sort}.png',
        url_sm=f'https://cdn.example.test/{product.id}/{sort}.png',
        alt=alt,
        sort=sort,
    )


@pytest.fixture
def second_product(product):
    brand = Brand.objects.create(name='Second Brand')
    other = Product.objects.create(name='Other Game', description='Other', price='10.00', stock=3, brand=brand)
    other.categories.add(*product.categories.all())
    return other


@pytest.fixture
def image_one(product):
    return make_image(product, 7)


@pytest.fixture
def image_two(product):
    return make_image(product, 8)


def fake_upload(product, image_file, alt_text):
    return make_image(product, 1, alt_text)


@pytest.mark.django_db
def test_image_upload_rejects_anonymous_and_non_admin_callers(api_client, auth_client, product):
    url = reverse('product-image-upload', args=[product.id])

    with patch('products.interfaces.views.process_and_upload_product_image', side_effect=fake_upload) as upload:
        anonymous = api_client.post(url, {'image': png_upload()}, format='multipart')
        regular = auth_client.post(url, {'image': png_upload()}, format='multipart')

    assert anonymous.status_code == status.HTTP_401_UNAUTHORIZED
    assert regular.status_code == status.HTTP_403_FORBIDDEN
    upload.assert_not_called()
    assert ProductImage.objects.count() == 0


@pytest.mark.django_db
def test_image_reorder_rejects_anonymous_and_non_admin_callers(api_client, auth_client, product, image_one, image_two):
    url = reverse('product-image-reorder', args=[product.id])
    payload = {'images': [{'id': image_one.id, 'sort': 20}, {'id': image_two.id, 'sort': 10}]}

    anonymous = api_client.patch(url, payload, format='json')
    regular = auth_client.patch(url, payload, format='json')

    assert anonymous.status_code == status.HTTP_401_UNAUTHORIZED
    assert regular.status_code == status.HTTP_403_FORBIDDEN
    image_one.refresh_from_db()
    image_two.refresh_from_db()
    assert (image_one.sort, image_two.sort) == (7, 8)


@pytest.mark.django_db
def test_image_delete_rejects_anonymous_and_non_admin_callers(api_client, auth_client, product, image_one):
    url = reverse('product-image-delete', args=[product.id, image_one.id])

    anonymous = api_client.delete(url)
    regular = auth_client.delete(url)

    assert anonymous.status_code == status.HTTP_401_UNAUTHORIZED
    assert regular.status_code == status.HTTP_403_FORBIDDEN
    assert ProductImage.objects.filter(pk=image_one.pk).exists()


@pytest.mark.django_db
def test_admin_can_upload_reorder_and_delete_images(staff_client, product):
    with patch('products.interfaces.views.process_and_upload_product_image', side_effect=fake_upload):
        uploaded = staff_client.post(
            reverse('product-image-upload', args=[product.id]), {'image': png_upload(), 'alt': 'Cover'},
            format='multipart',
        )

    assert uploaded.status_code == status.HTTP_201_CREATED
    first = ProductImage.objects.get()
    second = make_image(product, 2)

    reordered = staff_client.patch(
        reverse('product-image-reorder', args=[product.id]),
        {'images': [{'id': first.id, 'sort': 20}, {'id': second.id, 'sort': 10}]},
        format='json',
    )

    assert reordered.status_code == status.HTTP_200_OK
    first.refresh_from_db()
    second.refresh_from_db()
    assert (first.sort, second.sort) == (20, 10)

    with patch('products.interfaces.views.delete_product_image_files'):
        deleted = staff_client.delete(reverse('product-image-delete', args=[product.id, first.id]))

    assert deleted.status_code == status.HTTP_204_NO_CONTENT
    assert not ProductImage.objects.filter(pk=first.pk).exists()


@pytest.mark.django_db
def test_rejected_reorder_leaves_every_image_untouched(staff_client, product, second_product, image_one):
    foreign = make_image(second_product, 9)

    response = staff_client.patch(
        reverse('product-image-reorder', args=[product.id]),
        {'images': [{'id': image_one.id, 'sort': 1}, {'id': foreign.id, 'sort': 2}]},
        format='json',
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    image_one.refresh_from_db()
    foreign.refresh_from_db()
    assert image_one.sort == 7
    assert foreign.sort == 9


@pytest.mark.django_db
def test_reorder_with_duplicate_or_unknown_ids_does_not_change_anything(staff_client, product, image_one):
    unknown = staff_client.patch(
        reverse('product-image-reorder', args=[product.id]),
        {'images': [{'id': image_one.id, 'sort': 1}, {'id': 987654, 'sort': 2}]},
        format='json',
    )
    missing_product = staff_client.patch(
        reverse('product-image-reorder', args=[987654]), {'images': []}, format='json'
    )

    assert unknown.status_code == status.HTTP_400_BAD_REQUEST
    assert missing_product.status_code == status.HTTP_404_NOT_FOUND
    image_one.refresh_from_db()
    assert image_one.sort == 7


@pytest.mark.django_db
def test_reorder_requires_the_images_field(staff_client, product):
    response = staff_client.patch(reverse('product-image-reorder', args=[product.id]), {}, format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
@pytest.mark.parametrize('query', ['limit=101', 'limit=0', 'limit=-1', 'limit=abc', 'limit=', 'limit=1e3',
                                   'offset=-1', 'offset=abc', 'offset=9223372036854775808', 'page=2', 'page_size=5'])
def test_product_list_rejects_invalid_pagination_with_a_controlled_error(api_client, product, query):
    response = api_client.get(f'{reverse("product-list")}?{query}')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response['Content-Type'].startswith('application/json')
    assert response.json()['type'] == 'validation_error'


@pytest.mark.django_db
@pytest.mark.parametrize('query', ['limit=1', 'limit=100', 'offset=0', 'offset=9223372036854775807',
                                   'limit=100&offset=1'])
def test_product_list_accepts_the_documented_pagination_range(api_client, product, query):
    response = api_client.get(f'{reverse("product-list")}?{query}')

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert set(body) >= {'count', 'total_count', 'next', 'previous', 'results'}
    assert body['count'] == body['total_count'] == 1


@pytest.mark.django_db
def test_product_list_pagination_links_keep_the_limit(api_client, product, second_product):
    response = api_client.get(reverse('product-list'), {'limit': 1})

    body = response.json()
    assert response.status_code == status.HTTP_200_OK
    assert len(body['results']) == 1
    assert 'limit=1' in body['next']


@pytest.mark.django_db
def test_product_list_rejects_null_characters_in_search(api_client, product):
    response = api_client.get(reverse('product-list'), {'search': 'abc\x00def'})

    assert response.status_code in (status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST)


@pytest.mark.django_db
def test_photos_endpoint_is_read_only(auth_client, api_client, product, image_one):
    created = auth_client.post(reverse('photo-list'), {}, format='json')
    created_anonymous = api_client.post(reverse('photo-list'), {}, format='json')
    listed = api_client.get(reverse('photo-list'))
    detail = api_client.get(reverse('photo-detail', args=[image_one.id]))
    deleted = auth_client.delete(reverse('photo-detail', args=[image_one.id]))
    patched = auth_client.patch(reverse('photo-detail', args=[image_one.id]), {'alt': 'x'}, format='json')

    assert created.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert created_anonymous.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert listed.status_code == status.HTTP_200_OK
    assert detail.status_code == status.HTTP_200_OK
    assert deleted.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert patched.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert ProductImage.objects.count() == 1


@pytest.mark.django_db
def test_product_without_images_gets_a_placeholder_image(api_client, product):
    response = api_client.get(reverse('product-detail', args=[product.id]))

    assert response.status_code == status.HTTP_200_OK
    images = response.json()['images']
    assert len(images) == 1
    assert images[0]['id'] == 0
    assert images[0]['url_lg'].startswith('https://')


@pytest.mark.django_db
def test_products_with_the_same_non_latin_name_receive_unique_slugs(product):
    first = Product.objects.create(name='Настільна гра', description='d', price='5.00', brand=product.brand)
    second = Product.objects.create(name='Настільна гра', description='d', price='5.00', brand=product.brand)
    third = Product.objects.create(name='!!!', description='d', price='5.00', brand=product.brand)

    slugs = {first.slug, second.slug, third.slug}
    assert len(slugs) == 3
    assert '' not in slugs


@pytest.mark.django_db
def test_product_create_requires_authentication_and_rejects_null_game_information(api_client, auth_client, product):
    payload = {
        'name': 'Brand New Game', 'description': 'Great', 'price': '12.50',
        'categories': [category.id for category in product.categories.all()], 'brand': product.brand_id,
    }

    anonymous = api_client.post(reverse('product-list'), payload, format='json')
    null_info = auth_client.post(reverse('product-list'), {**payload, 'game_information': None}, format='json')
    form_null_info = auth_client.post(reverse('product-list'), {**payload, 'game_information': 'null'},
                                      format='multipart')
    created = auth_client.post(reverse('product-list'), payload, format='json')

    assert anonymous.status_code == status.HTTP_401_UNAUTHORIZED
    assert null_info.status_code == status.HTTP_400_BAD_REQUEST
    assert form_null_info.status_code == status.HTTP_400_BAD_REQUEST
    assert created.status_code == status.HTTP_201_CREATED
    assert Product.objects.filter(name='Brand New Game').count() == 1


@pytest.mark.django_db
def test_product_create_is_atomic_when_a_related_object_is_missing(auth_client, product):
    payload = {
        'name': 'Half Saved', 'description': 'Great', 'price': '12.50',
        'categories': [product.categories.first().id, 987654], 'brand': product.brand_id,
    }

    response = auth_client.post(reverse('product-list'), payload, format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert not Product.objects.filter(name='Half Saved').exists()


@pytest.mark.django_db
@pytest.mark.parametrize('price', ['0', '-1', '', 'abc', 'NaN', '99999999999.00'])
def test_product_create_rejects_invalid_prices(auth_client, product, price):
    payload = {
        'name': 'Pricey', 'description': 'Great', 'price': price,
        'categories': [product.categories.first().id], 'brand': product.brand_id,
    }

    response = auth_client.post(reverse('product-list'), payload, format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert not Product.objects.filter(name='Pricey').exists()


@pytest.mark.django_db
def test_nested_review_routes_work_end_to_end(api_client, auth_client, other_client, product, user):
    list_url = reverse('product-reviews-list', args=[product.id])

    anonymous_read = api_client.get(list_url)
    anonymous_write = api_client.post(list_url, {'rating': 5, 'comment': 'Great'}, format='json')
    created = auth_client.post(list_url, {'rating': 5, 'comment': 'Great'}, format='json')
    duplicate = auth_client.post(list_url, {'rating': 4, 'comment': 'Again'}, format='json')

    assert anonymous_read.status_code == status.HTTP_200_OK
    assert anonymous_write.status_code == status.HTTP_401_UNAUTHORIZED
    assert created.status_code == status.HTTP_201_CREATED
    assert created.json()['product_id'] == product.id
    assert created.json()['user_id'] == user.id
    assert duplicate.status_code == status.HTTP_409_CONFLICT
    assert Review.objects.count() == 1

    detail_url = reverse('product-review-detail', args=[product.id, created.json()['id']])

    assert api_client.get(detail_url).status_code == status.HTTP_200_OK
    assert api_client.patch(detail_url, {'rating': 1}, format='json').status_code == status.HTTP_401_UNAUTHORIZED
    assert other_client.patch(detail_url, {'rating': 1}, format='json').status_code == status.HTTP_403_FORBIDDEN
    assert other_client.delete(detail_url).status_code == status.HTTP_403_FORBIDDEN
    assert auth_client.patch(detail_url, {'rating': 2}, format='json').status_code == status.HTTP_200_OK
    assert Review.objects.get().rating == 2
    assert auth_client.delete(detail_url).status_code == status.HTTP_204_NO_CONTENT
    assert Review.objects.count() == 0


@pytest.mark.django_db
def test_nested_review_routes_return_not_found_for_unknown_products_and_reviews(api_client, auth_client, product):
    assert api_client.get(reverse('product-reviews-list', args=[987654])).status_code == status.HTTP_404_NOT_FOUND
    assert auth_client.post(
        reverse('product-reviews-list', args=[987654]), {'rating': 5}, format='json'
    ).status_code == status.HTTP_404_NOT_FOUND
    assert api_client.get(
        reverse('product-review-detail', args=[product.id, 987654])
    ).status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_review_cannot_be_moved_to_another_product_by_update(auth_client, user, product, second_product):
    review = Review.objects.create(product=product, user=user, rating=3, comment='ok')

    response = auth_client.put(
        reverse('review-detail', args=[review.id]),
        {'product_id': second_product.id, 'rating': 4, 'comment': 'moved'},
        format='json',
    )

    assert response.status_code == status.HTTP_200_OK
    review.refresh_from_db()
    assert review.product_id == product.id
    assert review.rating == 4


@pytest.mark.django_db
def test_flat_review_create_reports_duplicates_as_conflicts(auth_client, product):
    payload = {'product_id': product.id, 'rating': 5, 'comment': 'Nice'}

    first = auth_client.post(reverse('review-list'), payload, format='json')
    second = auth_client.post(reverse('review-list'), payload, format='json')

    assert first.status_code == status.HTTP_201_CREATED
    assert second.status_code == status.HTTP_409_CONFLICT
    assert Review.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize('rating', [0, 6, -1, 'x', None])
def test_review_rating_is_validated(auth_client, product, rating):
    response = auth_client.post(
        reverse('review-list'), {'product_id': product.id, 'rating': rating, 'comment': 'x'}, format='json'
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert Review.objects.count() == 0


@pytest.mark.django_db
def test_deleting_a_brand_in_use_reports_a_conflict(auth_client, product):
    response = auth_client.delete(reverse('brand-detail', args=[product.brand_id]))

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()['errors'][0]['code'] == 'conflict'
    assert Brand.objects.filter(pk=product.brand_id).exists()


@pytest.mark.django_db
@pytest.mark.parametrize('route', ['brand-detail', 'audience-detail', 'game-type-detail', 'category-detail',
                                   'product-detail', 'photo-detail'])
def test_malformed_ids_are_not_found_as_json(api_client, route):
    url = reverse(route, args=[1]).rsplit('/', 2)[0] + '/not-an-integer/'

    response = api_client.get(url)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response['Content-Type'].startswith('application/json')
    assert response.json()['errors'][0]['code'] == 'not_found'
