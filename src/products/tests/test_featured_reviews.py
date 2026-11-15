from types import SimpleNamespace

import pytest
from django.urls import reverse
from rest_framework import status

from products.infrastructure.models import Brand, Product, Review
from products.interfaces.serializers import DEFAULT_REVIEW_AUTHOR_NAME, build_review_author_name
from products.interfaces.views import (
    FEATURED_REVIEW_MIN_COMMENT_LENGTH,
    FEATURED_REVIEW_MIN_RATING,
    FEATURED_REVIEWS_COUNT,
)

GOOD_COMMENT = 'Great game for the whole family, we play it every weekend.'
FEATURED_FIELDS = {'id', 'product_id', 'product_name', 'user_name', 'rating', 'comment', 'created_at'}


@pytest.fixture
def make_product(db):
    brand = Brand.objects.create(name='Featured Brand')
    counter = {'value': 0}

    def build(name=None):
        counter['value'] += 1
        return Product.objects.create(
            name=name or f'Game {counter["value"]}',
            description='Description',
            price='10.00',
            stock=5,
            brand=brand,
        )

    return build


@pytest.fixture
def make_user(user_model):
    counter = {'value': 0}

    def build(first_name='Daniel', last_name='Taylor'):
        counter['value'] += 1
        return user_model.objects.create_user(
            username=f'reviewer{counter["value"]}',
            email=f'reviewer{counter["value"]}@example.com',
            password='testpass123',
            first_name=first_name,
            last_name=last_name,
        )

    return build


@pytest.fixture
def make_review(make_user, make_product):
    def build(product=None, user=None, rating=5, comment=GOOD_COMMENT):
        return Review.objects.create(
            product=product or make_product(),
            user=user or make_user(),
            rating=rating,
            comment=comment,
        )

    return build


def featured(api_client):
    response = api_client.get(reverse('review-featured'))
    assert response.status_code == status.HTTP_200_OK
    return response.json()


@pytest.mark.parametrize(
    'first_name,last_name,expected',
    [
        ('Daniel', 'Taylor', 'Daniel T.'),
        ('  Emma ', '  rogers ', 'Emma R.'),
        ('Michael', '', 'Michael'),
        ('Олена', 'ковальчук', 'Олена К.'),
        ('', 'Taylor', DEFAULT_REVIEW_AUTHOR_NAME),
        ('', '', DEFAULT_REVIEW_AUTHOR_NAME),
        ('   ', 'Taylor', DEFAULT_REVIEW_AUTHOR_NAME),
    ],
)
def test_review_author_name_is_first_name_and_last_initial(first_name, last_name, expected):
    user = SimpleNamespace(first_name=first_name, last_name=last_name)

    assert build_review_author_name(user) == expected


def test_review_author_name_falls_back_for_missing_user():
    assert build_review_author_name(None) == DEFAULT_REVIEW_AUTHOR_NAME


@pytest.mark.django_db
def test_featured_reviews_are_public_and_expose_only_safe_fields(api_client, make_review, make_product, make_user):
    catan = make_product('Catan')
    review = make_review(product=catan, user=make_user('Daniel', 'Taylor'))

    payload = featured(api_client)

    assert len(payload) == 1
    assert set(payload[0]) == FEATURED_FIELDS
    assert payload[0]['id'] == review.id
    assert payload[0]['product_id'] == catan.id
    assert payload[0]['product_name'] == 'Catan'
    assert payload[0]['user_name'] == 'Daniel T.'
    assert payload[0]['rating'] == 5
    assert payload[0]['comment'] == GOOD_COMMENT
    serialized = str(payload)
    assert 'reviewer' not in serialized
    assert '@example.com' not in serialized


@pytest.mark.django_db
def test_featured_reviews_are_empty_when_nothing_qualifies(api_client):
    assert featured(api_client) == []


@pytest.mark.django_db
def test_featured_reviews_never_exceed_the_limit(api_client, make_review):
    created = {make_review().id for _ in range(FEATURED_REVIEWS_COUNT + 3)}

    payload = featured(api_client)

    assert len(payload) == FEATURED_REVIEWS_COUNT
    assert len({item['id'] for item in payload}) == FEATURED_REVIEWS_COUNT
    assert {item['id'] for item in payload} <= created


@pytest.mark.django_db
def test_featured_reviews_take_at_most_one_review_per_game(api_client, make_review, make_product):
    crowded = make_product('Crowded')
    for _ in range(5):
        make_review(product=crowded)
    make_review(product=make_product('Second'))
    make_review(product=make_product('Third'))

    payload = featured(api_client)

    product_ids = [item['product_id'] for item in payload]
    assert len(payload) == 3
    assert len(set(product_ids)) == 3


@pytest.mark.django_db
def test_featured_reviews_skip_low_rated_short_blank_and_anonymous_reviews(
    api_client, make_review, make_user, make_product
):
    good = make_review()
    make_review(rating=3)
    make_review(rating=1)
    make_review(comment='Nice!')
    make_review(comment='')
    make_review(comment=' ' * 60)
    make_review(user=make_user(first_name='', last_name='Taylor'))
    Review.objects.create(product=make_product(), user=None, rating=5, comment=GOOD_COMMENT)

    payload = featured(api_client)

    assert [item['id'] for item in payload] == [good.id]


@pytest.mark.django_db
@pytest.mark.parametrize(
    'rating,length,expected',
    [
        (FEATURED_REVIEW_MIN_RATING, FEATURED_REVIEW_MIN_COMMENT_LENGTH, True),
        (FEATURED_REVIEW_MIN_RATING, FEATURED_REVIEW_MIN_COMMENT_LENGTH - 1, False),
        (FEATURED_REVIEW_MIN_RATING - 1, FEATURED_REVIEW_MIN_COMMENT_LENGTH, False),
        (5, FEATURED_REVIEW_MIN_COMMENT_LENGTH + 100, True),
    ],
)
def test_featured_reviews_thresholds(api_client, make_review, rating, length, expected):
    review = make_review(rating=rating, comment='x' * length)

    assert ([item['id'] for item in featured(api_client)] == [review.id]) is expected


@pytest.mark.django_db
def test_featured_reviews_selection_is_random(api_client, make_review):
    for _ in range(12):
        make_review()

    seen = set()
    for _ in range(25):
        seen.update(item['id'] for item in featured(api_client))

    assert len(seen) > FEATURED_REVIEWS_COUNT


@pytest.mark.django_db
def test_featured_reviews_use_a_single_query(api_client, make_review, django_assert_num_queries):
    for _ in range(6):
        make_review()

    with django_assert_num_queries(1):
        response = api_client.get(reverse('review-featured'))

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_featured_route_does_not_shadow_the_review_detail_route(api_client, make_review):
    review = make_review()

    assert reverse('review-featured') == '/api/reviews/featured/'
    detail = api_client.get(reverse('review-detail', args=[review.id]))

    assert detail.status_code == status.HTTP_200_OK
    assert detail.json()['id'] == review.id
    assert detail.json()['user_name'] == 'Daniel T.'


@pytest.mark.django_db
@pytest.mark.parametrize('method', ['post', 'put', 'patch', 'delete'])
def test_featured_reviews_are_read_only(api_client, auth_client, method):
    anonymous = getattr(api_client, method)(reverse('review-featured'), {}, format='json')
    authenticated = getattr(auth_client, method)(reverse('review-featured'), {}, format='json')

    assert anonymous.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert authenticated.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.django_db
def test_flat_review_list_returns_user_name_next_to_user_id(api_client, make_review, make_user, make_product):
    product = make_product('Catan')
    author = make_user('Daniel', 'Taylor')
    make_review(product=product, user=author)
    Review.objects.create(product=make_product(), user=None, rating=5, comment=GOOD_COMMENT)

    response = api_client.get(reverse('review-list'))

    assert response.status_code == status.HTTP_200_OK
    by_user = {item['user_id']: item for item in response.json()['results']}
    assert by_user[author.id]['user_name'] == 'Daniel T.'
    assert by_user[None]['user_name'] == DEFAULT_REVIEW_AUTHOR_NAME


@pytest.mark.django_db
def test_review_list_does_not_query_the_author_for_every_row(api_client, make_review, django_assert_max_num_queries):
    for _ in range(6):
        make_review()

    with django_assert_max_num_queries(3):
        response = api_client.get(reverse('review-list'))

    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()['results']) == 6


@pytest.mark.django_db
def test_nested_review_list_returns_user_name(api_client, make_review, make_product, make_user):
    product = make_product('Catan')
    make_review(product=product, user=make_user('Emma', 'Rogers'))

    response = api_client.get(reverse('product-reviews-list', args=[product.id]))

    assert response.status_code == status.HTTP_200_OK
    assert [item['user_name'] for item in response.json()['results']] == ['Emma R.']


@pytest.mark.django_db
def test_created_review_returns_user_name_and_ignores_a_client_supplied_one(auth_client, user, product):
    response = auth_client.post(
        reverse('review-list'),
        {'product_id': product.id, 'rating': 5, 'comment': 'x', 'user_name': 'Somebody Else'},
        format='json',
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()['user_id'] == user.id
    assert response.json()['user_name'] == 'Test U.'
