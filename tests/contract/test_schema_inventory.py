import pytest
from django.urls import reverse


pytestmark = pytest.mark.contract


def test_runtime_openapi_schema_is_json_and_contains_operations(client):
    response = client.get(reverse("schema"))

    assert response.status_code == 200
    assert response["Content-Type"].split(";", 1)[0] in {
        "application/json",
        "application/vnd.oai.openapi+json",
    }
    schema = response.json()
    assert schema["openapi"].startswith("3.")
    assert schema["info"]["title"] == "Board Game Shop"
    assert schema["paths"]
    assert any(
        method in path_item
        for path_item in schema["paths"].values()
        for method in {"get", "post", "put", "patch", "delete"}
    )


def test_every_documented_operation_declares_responses(client):
    schema = client.get(reverse("schema")).json()
    operations = [
        operation
        for path_item in schema["paths"].values()
        for method, operation in path_item.items()
        if method in {"get", "post", "put", "patch", "delete"}
    ]

    assert operations
    assert all(operation.get("operationId") for operation in operations)
    assert all(operation.get("responses") for operation in operations)


@pytest.mark.bug
def test_current_schema_defect_emits_array_instead_of_oauth_user_schema(client):
    schema = client.get(reverse("schema")).json()

    user_schema = schema["paths"]["/api/users/oauth/"]["post"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["properties"]["user"]

    assert user_schema == ["id", "email", "first_name", "last_name", "date_joined"]
