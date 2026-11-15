import json

import pytest
from drf_spectacular.drainage import GENERATOR_STATS
from drf_spectacular.generators import SchemaGenerator
from drf_spectacular.validation import validate_schema
from jsonschema import Draft4Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT4
from django.urls import reverse
from rest_framework import status

from orders.infrastructure.models import DeliveryOption, Order
from products.infrastructure.models import Product, ProductImage, Review


def normalize(node, direction):
    hidden_flag = 'writeOnly' if direction == 'response' else 'readOnly'
    if isinstance(node, dict):
        result = {key: normalize(value, direction) for key, value in node.items()}
        properties = result.get('properties')
        if isinstance(properties, dict):
            hidden = {name for name, value in properties.items() if isinstance(value, dict) and value.get(hidden_flag)}
            if hidden:
                result['properties'] = {name: value for name, value in properties.items() if name not in hidden}
                if 'required' in result:
                    result['required'] = [name for name in result['required'] if name not in hidden]
                    if not result['required']:
                        result.pop('required')
        if 'oneOf' in result:
            result['anyOf'] = result.pop('oneOf')
        if result.get('nullable') is True:
            result.pop('nullable')
            return {'anyOf': [result, {'type': 'null'}]}
        result.pop('nullable', None)
        return result
    if isinstance(node, list):
        return [normalize(item, direction) for item in node]
    return node


def pointer_escape(value):
    return value.replace('~', '~0').replace('/', '~1')


@pytest.fixture(scope='module')
def generated():
    GENERATOR_STATS.reset()
    document = json.loads(json.dumps(SchemaGenerator().get_schema(request=None, public=True)))
    warnings = dict(GENERATOR_STATS._warn_cache)
    errors = dict(GENERATOR_STATS._error_cache)
    return document, warnings, errors


@pytest.fixture(scope='module')
def schema(generated):
    return generated[0]


def build_registry(schema, direction):
    resource = Resource.from_contents(normalize(schema, direction), default_specification=DRAFT4)
    return Registry().with_resource('urn:openapi', resource)


@pytest.fixture(scope='module')
def registry(schema):
    return {'request': build_registry(schema, 'request'), 'response': build_registry(schema, 'response')}


def operation(schema, path, method):
    return schema['paths'][path][method]


def response_schema_pointer(path, method, code):
    return (
        f'urn:openapi#/paths/{pointer_escape(path)}/{method}/responses/{code}/content/application~1json/schema'
    )


def request_schema_pointer(path, method):
    return f'urn:openapi#/paths/{pointer_escape(path)}/{method}/requestBody/content/application~1json/schema'


def assert_documented_response(schema, registry, path, method, response):
    code = str(response.status_code)
    documented = operation(schema, path, method)['responses']
    assert code in documented, f'{method} {path} answered {code}, documented: {sorted(documented)}'
    content = documented[code].get('content', {})
    if not content:
        return
    assert response['Content-Type'].split(';')[0] in content, (
        f'{method} {path} {code} answered {response["Content-Type"]}, documented: {sorted(content)}'
    )
    validator = Draft4Validator({'$ref': response_schema_pointer(path, method, code)}, registry=registry['response'])
    errors = sorted(validator.iter_errors(response.json()), key=lambda error: list(error.path))
    assert not errors, f'{method} {path} {code}: {errors[0].message} at {list(errors[0].path)}'


def assert_matches_request_schema(schema, registry, path, method, body):
    validator = Draft4Validator({'$ref': request_schema_pointer(path, method)}, registry=registry['request'])
    return list(validator.iter_errors(body))


def test_schema_generates_without_warnings_or_errors(generated):
    _, warnings, errors = generated

    assert warnings == {}
    assert errors == {}


def test_schema_is_a_valid_openapi_document(schema):
    validate_schema(schema)


def test_every_response_property_is_a_schema_object_or_reference(schema):
    def walk(node, trail):
        if isinstance(node, dict):
            properties = node.get('properties')
            if isinstance(properties, dict):
                for name, value in properties.items():
                    assert isinstance(value, dict), f'{trail}.{name} is {type(value).__name__}'
            for key, value in node.items():
                walk(value, f'{trail}.{key}')
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f'{trail}[{index}]')

    walk(schema, '#')


def test_order_list_declares_numeric_fields_as_numbers(schema):
    properties = schema['components']['schemas']['OrderList']['properties']

    assert properties['subtotal']['type'] == 'number'
    assert properties['shipping_cost']['type'] == 'number'
    if 'product_count' in properties:
        assert properties['product_count']['type'] == 'integer'
    for name, value in properties.items():
        assert set(value) & {'type', '$ref', 'allOf', 'oneOf', 'anyOf'}, f'OrderList.{name} has no type'


def test_order_create_documents_the_buyer_contact_fields_for_the_confirmation_email(schema):
    post = operation(schema, '/api/orders/', 'post')
    request_ref = post['requestBody']['content']['application/json']['schema']['$ref']
    request_schema = schema['components']['schemas'][request_ref.rsplit('/', 1)[1]]
    properties = request_schema['properties']

    assert {'type': 'string', 'format': 'email', 'maxLength': 254} in properties['email']['oneOf']
    assert properties['phone']['type'] == 'string'
    for name in ('email', 'phone'):
        assert properties[name]['writeOnly'] is True
        assert properties[name]['nullable'] is True
        assert properties[name]['description']
        assert name not in request_schema.get('required', [])
    assert 'email' in post['description']


def test_payment_intent_is_documented_with_request_and_response_serializers(schema):
    post = operation(schema, '/api/orders/create-payment-intent/', 'post')
    request_ref = post['requestBody']['content']['application/json']['schema']['$ref']
    response_ref = post['responses']['200']['content']['application/json']['schema']['$ref']
    request_schema = schema['components']['schemas'][request_ref.rsplit('/', 1)[1]]
    response_schema = schema['components']['schemas'][response_ref.rsplit('/', 1)[1]]

    assert request_schema['properties']['amount']['type'] == 'integer'
    assert request_schema['required'] == ['amount']
    assert response_schema['properties']['clientSecret']['type'] == 'string'
    assert '400' in post['responses']
    assert '401' in post['responses']


def test_oauth_response_user_property_is_a_valid_schema_object(schema):
    content = operation(schema, '/api/users/oauth/', 'post')['responses']['200']['content']['application/json']
    reference = content['schema']['$ref'].rsplit('/', 1)[1]
    properties = schema['components']['schemas'][reference]['properties']

    assert isinstance(properties['user'], dict)
    assert not isinstance(properties['user'], list)
    assert set(properties['user']) & {'$ref', 'type', 'allOf'}


def test_authenticated_cart_get_is_not_paginated(schema):
    get = operation(schema, '/api/cart/', 'get')

    assert get.get('parameters', []) == []
    reference = get['responses']['200']['content']['application/json']['schema']['$ref']
    assert reference.endswith('/Cart')


def test_cart_item_operations_document_their_statuses(schema):
    item = schema['paths']['/api/cart/item/']

    assert {'200', '201', '400', '401'} <= set(item['post']['responses'])
    assert {'200', '204', '400', '401', '404'} <= set(item['patch']['responses'])
    assert {'204', '400', '401', '404'} <= set(item['delete']['responses'])
    assert 'product_id' in schema['components']['schemas']['CartItemUpdate']['required']
    assert 'quantity' in schema['components']['schemas']['CartItemUpdate']['required']


def test_token_request_schema_requires_both_credentials(schema):
    components = schema['components']['schemas']['CustomTokenObtainPair']

    assert set(components['required']) == {'email', 'password'}
    assert components['properties']['email']['minLength'] >= 1
    assert components['properties']['password']['minLength'] >= 1


def test_token_endpoint_rejects_what_the_request_schema_rejects(schema, registry, api_client):
    body = {}
    errors = assert_matches_request_schema(schema, registry, '/api/users/token/', 'post', body)

    response = api_client.post(reverse('token_obtain_pair'), body, format='json')

    assert errors
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
@pytest.mark.parametrize('body', [{}, {'email': '', 'password': ''}, {'email': 'a@example.com'}, {'password': 'x'}])
def test_schema_invalid_token_requests_get_validation_errors(schema, registry, api_client, body):
    assert assert_matches_request_schema(schema, registry, '/api/users/token/', 'post', body)

    response = api_client.post(reverse('token_obtain_pair'), body, format='json')

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
@pytest.mark.parametrize('route,field', [
    ('brand-list', 'name'),
    ('audience-list', 'name'),
    ('game-type-list', 'name'),
])
def test_blank_names_are_invalid_in_schema_and_at_runtime(schema, registry, auth_client, route, field):
    path = {'brand-list': '/api/brands/', 'audience-list': '/api/audiences/',
            'game-type-list': '/api/game-types/'}[route]
    body = {field: ''}

    assert assert_matches_request_schema(schema, registry, path, 'post', body)
    assert auth_client.post(reverse(route), body, format='json').status_code == status.HTTP_400_BAD_REQUEST


def test_product_list_query_parameters_describe_the_runtime_policy(schema):
    parameters = {item['name']: item for item in operation(schema, '/api/products/', 'get')['parameters']}

    assert parameters['limit']['schema']['minimum'] == 1
    assert parameters['limit']['schema']['maximum'] == 100
    assert parameters['offset']['schema']['minimum'] == 0
    assert parameters['search']['allowEmptyValue'] is True
    assert 'page' not in parameters
    assert '400' in operation(schema, '/api/products/', 'get')['responses']


def test_status_codes_and_redirects_are_documented(schema):
    assert '201' in operation(schema, '/api/products/', 'post')['responses']
    assert '204' in operation(schema, '/api/categories/{id}/', 'delete')['responses']
    assert '401' in operation(schema, '/api/users/token/refresh/', 'post')['responses']
    assert '302' in operation(schema, '/api/users/reset-password/', 'get')['responses']
    assert '204' in operation(schema, '/api/reviews/{id}/', 'delete')['responses']
    assert '200' not in operation(schema, '/api/reviews/{id}/', 'delete')['responses']


def test_delete_operations_document_conflicts_but_reads_do_not(schema):
    assert '409' in operation(schema, '/api/brands/{id}/', 'delete')['responses']
    assert '409' not in operation(schema, '/api/brands/{id}/', 'get')['responses']


@pytest.mark.django_db
def test_cart_responses_match_the_documented_schemas(schema, registry, auth_client, user, product):
    added = auth_client.post(reverse('cart-item'), {'product_id': product.id, 'quantity': 2}, format='json')
    again = auth_client.post(reverse('cart-item'), {'product_id': product.id}, format='json')
    listed = auth_client.get(reverse('cart-list-add'))
    updated = auth_client.patch(reverse('cart-item'), {'product_id': product.id, 'quantity': 5}, format='json')
    invalid = auth_client.post(reverse('cart-item'), {'product_id': product.id, 'quantity': 0}, format='json')
    missing = auth_client.patch(reverse('cart-item'), {'product_id': 987654, 'quantity': 5}, format='json')

    assert_documented_response(schema, registry, '/api/cart/item/', 'post', added)
    assert_documented_response(schema, registry, '/api/cart/item/', 'post', again)
    assert_documented_response(schema, registry, '/api/cart/', 'get', listed)
    assert_documented_response(schema, registry, '/api/cart/item/', 'patch', updated)
    assert_documented_response(schema, registry, '/api/cart/item/', 'post', invalid)
    assert_documented_response(schema, registry, '/api/cart/item/', 'patch', missing)
    assert added.status_code == status.HTTP_201_CREATED
    assert again.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_anonymous_cart_errors_match_the_documented_envelope(schema, registry, api_client):
    response = api_client.get(reverse('cart-list-add'))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert_documented_response(schema, registry, '/api/cart/', 'get', response)


@pytest.mark.django_db
def test_catalog_responses_match_the_documented_schemas(schema, registry, api_client, product):
    category = product.categories.get()
    category.image = ''
    category.save()
    ProductImage.objects.create(product=product, url_original='https://cdn.example.test/a.png',
                                url_lg='https://cdn.example.test/a.png', url_md='https://cdn.example.test/a.png',
                                url_sm='https://cdn.example.test/a.png', sort=1)
    bare = Product.objects.create(name='Bare', description='No images', price='1.00', brand=product.brand)
    bare.categories.add(category)

    category_detail = api_client.get(reverse('category-detail', args=[category.id]))
    category_list = api_client.get(reverse('category-list-create'))
    product_list = api_client.get(reverse('product-list'))
    with_images = api_client.get(reverse('product-detail', args=[product.id]))
    placeholder = api_client.get(reverse('product-detail', args=[bare.id]))
    invalid_limit = api_client.get(reverse('product-list'), {'limit': 101})
    missing = api_client.get(reverse('product-detail', args=[987654]))

    assert_documented_response(schema, registry, '/api/categories/{id}/', 'get', category_detail)
    assert_documented_response(schema, registry, '/api/categories/', 'get', category_list)
    assert_documented_response(schema, registry, '/api/products/', 'get', product_list)
    assert_documented_response(schema, registry, '/api/products/{id}/', 'get', with_images)
    assert_documented_response(schema, registry, '/api/products/{id}/', 'get', placeholder)
    assert_documented_response(schema, registry, '/api/products/', 'get', invalid_limit)
    assert_documented_response(schema, registry, '/api/products/{id}/', 'get', missing)
    assert placeholder.json()['images'][0]['id'] == 0
    assert invalid_limit.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_review_and_conflict_responses_match_the_documented_schemas(schema, registry, auth_client, product):
    created = auth_client.post(reverse('review-list'), {'product_id': product.id, 'rating': 5, 'comment': 'x'},
                               format='json')
    duplicate = auth_client.post(reverse('review-list'), {'product_id': product.id, 'rating': 5, 'comment': 'x'},
                                 format='json')
    review_id = created.json()['id']
    detail = auth_client.get(reverse('review-detail', args=[review_id]))
    brand_conflict = auth_client.delete(reverse('brand-detail', args=[product.brand_id]))

    assert_documented_response(schema, registry, '/api/reviews/', 'post', created)
    assert_documented_response(schema, registry, '/api/reviews/', 'post', duplicate)
    assert_documented_response(schema, registry, '/api/reviews/{id}/', 'get', detail)
    assert_documented_response(schema, registry, '/api/brands/{id}/', 'delete', brand_conflict)
    assert Review.objects.count() == 1


def test_featured_reviews_endpoint_is_documented_for_swagger(schema):
    get = operation(schema, '/api/reviews/featured/', 'get')
    ok = get['responses']['200']['content']['application/json']
    featured = schema['components']['schemas']['FeaturedReview']

    assert get['tags'] == ['Reviews']
    assert get['summary']
    assert get['description']
    assert {} in get['security']
    assert ok['schema'] == {'type': 'array', 'items': {'$ref': '#/components/schemas/FeaturedReview'}}
    assert ok['examples']
    assert set(featured['properties']) == {
        'id', 'product_id', 'product_name', 'user_name', 'rating', 'comment', 'created_at'
    }
    assert featured['properties']['user_name']['type'] == 'string'
    assert featured['properties']['user_name']['description']
    assert set(featured['required']) == set(featured['properties'])


@pytest.mark.parametrize('component', ['Review', 'ReviewWrite'])
def test_review_schemas_document_user_name_next_to_user_id(schema, component):
    properties = schema['components']['schemas'][component]['properties']

    assert properties['user_name']['type'] == 'string'
    assert properties['user_name']['readOnly'] is True
    assert properties['user_name']['description']
    assert 'user_id' in properties


@pytest.mark.django_db
def test_featured_and_listed_reviews_match_the_documented_schemas(schema, registry, api_client, user, product):
    Review.objects.create(product=product, user=user, rating=5, comment='A' * 40)
    nested_url = reverse('product-reviews-list', args=[product.id])
    nested_path = nested_url.replace(f'/{product.id}/', '/{product_id}/')

    featured = api_client.get(reverse('review-featured'))
    flat = api_client.get(reverse('review-list'))
    nested = api_client.get(nested_url)

    assert_documented_response(schema, registry, '/api/reviews/featured/', 'get', featured)
    assert_documented_response(schema, registry, '/api/reviews/', 'get', flat)
    assert_documented_response(schema, registry, nested_path, 'get', nested)
    assert featured.json()[0]['user_name'] == 'Test U.'
    assert flat.json()['results'][0]['user_name'] == 'Test U.'
    assert nested.json()['results'][0]['user_name'] == 'Test U.'


@pytest.mark.django_db
def test_order_responses_match_the_documented_schemas(schema, registry, auth_client, user, user_cart):
    option = DeliveryOption.objects.create(name='Contract', description='d', price='5.00', estimated_days=1,
                                           is_active=True)
    created = auth_client.post(
        reverse('order-list-create'),
        {'cart_id': user_cart.id, 'delivery_option_id': option.id, 'shipping_address': 'Baker Street 221B'},
        format='json',
    )
    listed = auth_client.get(reverse('order-list-create'))
    invalid = auth_client.post(reverse('order-list-create'), {'delivery_option_id': option.id}, format='json')

    assert created.status_code == status.HTTP_201_CREATED
    assert Order.objects.count() == 1
    assert_documented_response(schema, registry, '/api/orders/', 'post', created)
    assert_documented_response(schema, registry, '/api/orders/', 'get', listed)
    assert_documented_response(schema, registry, '/api/orders/', 'post', invalid)


@pytest.mark.django_db
@pytest.mark.parametrize('route', ['brand-detail', 'audience-detail', 'game-type-detail', 'product-detail',
                                   'category-detail'])
def test_malformed_typed_paths_return_json_not_found(api_client, route):
    path = reverse(route, args=[1]).rsplit('/', 2)[0] + '/not-an-integer/'

    response = api_client.get(path)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response['Content-Type'].startswith('application/json')
    assert response.json() == {
        'type': 'client_error',
        'errors': [{'code': 'not_found', 'detail': 'Not found.', 'attr': None}],
    }


@pytest.mark.django_db
def test_unknown_api_paths_return_json_not_found(api_client):
    response = api_client.get('/api/does-not-exist/')

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response['Content-Type'].startswith('application/json')
