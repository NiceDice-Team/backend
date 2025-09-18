# src/users/tests/test_categories_models.py
from django.core.exceptions import ValidationError
import pytest

@pytest.mark.positive
@pytest.mark.django_db
@pytest.mark.parametrize(
    "name, slug, description, image",
    [
        ("Electronics", "electronics", "Category for electronic items", "http://example.com/image1.jpg"),
        ("Books", "books", "Category for books", "http://example.com/image2.jpg"),
        ("Clothing", "clothing", "Category for clothing items", "http://example.com/image3.jpg"),
    ]
)
def test_category_creation_parametrized(category_model, name, slug, description, image):
    """Check category creation with various attributes."""
    category = category_model.objects.create(
        name=name,
        slug=slug,
        description=description,
        image=image,
    )
    # Assertions
    assert category.name == name
    assert category.slug == slug
    assert category.description == description
    assert category.image == image

@pytest.mark.negative
@pytest.mark.django_db
@pytest.mark.parametrize(
    "name, slug, expected_exception",
    [
        ("", "slug", ValidationError),           # Empty name
        (None, "slug", ValidationError),         # None name
    ]
)
def test_category_creation_invalid_fields(category_model, name, slug, expected_exception):
    """Ensure that creating a category with invalid fields raises an exception."""
    with pytest.raises(expected_exception):
        category_model.objects.create(
            name=name,
            slug=slug,
            description="desc",
            image="http://example.com/image.jpg"
        )
