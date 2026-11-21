import pytest
from django.urls import reverse
from rest_framework import status

DOCUMENTED_PAYLOAD = {
    'name': 'Created Category',
    'slug': 'created-category',
    'description': 'Created via API',
    'image': 'http://example.test/image.jpg',
}


@pytest.mark.django_db
def test_category_is_created_from_the_documented_payload_without_server_fields(auth_client, category_model):
    response = auth_client.post(reverse('category-list-create'), DOCUMENTED_PAYLOAD, format='json')

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    assert body['name'] == 'Created Category'
    assert body['id'] > 0
    assert body['creationAt']
    assert body['updatedAt']
    assert category_model.objects.filter(name='Created Category').count() == 1


@pytest.mark.django_db
def test_category_server_fields_supplied_by_the_client_are_ignored(auth_client, category_model):
    payload = {
        'id': 999,
        'name': 'Spoofed',
        'image': 'https://example.test/category.png',
        'creationAt': '2001-01-01T00:00:00Z',
        'updatedAt': '2001-01-01T00:00:00Z',
    }

    response = auth_client.post(reverse('category-list-create'), payload, format='json')

    assert response.status_code == status.HTTP_201_CREATED
    created = category_model.objects.get(name='Spoofed')
    assert created.pk != 999
    assert created.created_at.year != 2001


@pytest.mark.django_db
def test_category_creation_requires_authentication(api_client, category_model):
    response = api_client.post(reverse('category-list-create'), DOCUMENTED_PAYLOAD, format='json')

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert category_model.objects.count() == 0


@pytest.mark.django_db
def test_category_with_blank_image_is_returned_as_is(auth_client, category_model):
    category = category_model.objects.create(name='No Image', image='')

    response = auth_client.get(reverse('category-detail', args=[category.id]))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()['image'] == ''


@pytest.mark.django_db
def test_punctuation_only_name_colliding_with_an_empty_slug_is_rejected(auth_client, category_model):
    category_model.objects.create(name='[]')
    payload = {
        'id': 999,
        'name': '{}',
        'image': 'https://example.test/category.png',
        'creationAt': '2026-10-03T00:00:00Z',
        'updatedAt': '2026-10-03T00:00:00Z',
    }

    response = auth_client.post(reverse('category-list-create'), payload, format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response['Content-Type'].startswith('application/json')
    assert category_model.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize('name', ['[]', '!!!', '   ', '---'])
def test_names_without_letters_or_digits_are_rejected(auth_client, category_model, name):
    response = auth_client.post(reverse('category-list-create'), {'name': name}, format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert category_model.objects.count() == 0


@pytest.mark.django_db
def test_names_with_the_same_derived_slug_are_rejected(auth_client, category_model):
    category_model.objects.create(name='Board Games')

    response = auth_client.post(reverse('category-list-create'), {'name': 'board-games'}, format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert category_model.objects.count() == 1


@pytest.mark.django_db
def test_non_latin_names_get_distinct_slugs_instead_of_colliding(auth_client, category_model):
    first = auth_client.post(reverse('category-list-create'), {'name': 'Настільні ігри'}, format='json')
    second = auth_client.post(reverse('category-list-create'), {'name': 'Карткові ігри'}, format='json')

    assert first.status_code == status.HTTP_201_CREATED
    assert second.status_code == status.HTTP_201_CREATED
    slugs = set(category_model.objects.values_list('slug', flat=True))
    assert len(slugs) == 2
    assert '' not in slugs


@pytest.mark.django_db
def test_renaming_a_category_to_a_colliding_name_is_rejected(auth_client, category_model):
    category_model.objects.create(name='Board Games')
    other = category_model.objects.create(name='Card Games')

    response = auth_client.patch(reverse('category-detail', args=[other.id]), {'name': 'Board Games'},
                                 format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    other.refresh_from_db()
    assert other.name == 'Card Games'


@pytest.mark.django_db
def test_category_delete_returns_no_content(auth_client, category_model):
    category = category_model.objects.create(name='To Delete')

    response = auth_client.delete(reverse('category-detail', args=[category.id]))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not category_model.objects.filter(pk=category.pk).exists()


@pytest.mark.django_db
def test_deleting_a_category_keeps_its_products(auth_client, product):
    category = product.categories.get()

    response = auth_client.delete(reverse('category-detail', args=[category.id]))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    product.refresh_from_db()
    assert product.categories.count() == 0
