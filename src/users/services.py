from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

USERNAME_MAX_LENGTH = 150


def find_user_by_email(email):
    if not email or not isinstance(email, str):
        return None
    user_model = get_user_model()
    candidates = user_model.objects.filter(email__iexact=email)
    return candidates.filter(email=email).first() or candidates.order_by('id').first()


def generate_unique_username(base):
    user_model = get_user_model()
    base = (base or 'user').strip() or 'user'
    base = base[:USERNAME_MAX_LENGTH - 12]
    candidate = base
    counter = 1
    while user_model.objects.filter(username__iexact=candidate).exists():
        candidate = f"{base}_{counter}"
        counter += 1
    return candidate


def build_activation_url(request, user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    activation_path = reverse('activate', kwargs={'uidb64': uid, 'token': token})
    return request.build_absolute_uri(activation_path)
