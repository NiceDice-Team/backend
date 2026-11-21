import logging
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.core.validators import validate_email
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.formats import date_format

from orders.cancellation import make_cancel_token

logger = logging.getLogger(__name__)

ORDER_STATUS_LABELS = {
    'pending': 'Pending',
    'processing': 'Processing',
    'shipped': 'Shipped',
    'delivered': 'Delivered',
    'cancelled': 'Cancelled',
}

LOGO_ICON_PLACEHOLDER = 'https://placehold.co/48x48?text=D%26D'
LOGO_IMAGE_PLACEHOLDER = 'https://placehold.co/150x40?text=Dice+%26+Decks'
CANCEL_ICON_PLACEHOLDER = 'https://placehold.co/64x64?text=48h'
PRODUCT_IMAGE_PLACEHOLDER = 'https://placehold.co/56x56?text=No+Image'

ADDRESS_SEPARATORS = re.compile(r'[\n,;]+')
STOREFRONT_ADDRESS_MIN_PARTS = 6


def format_money(amount):
    try:
        amount = Decimal(str(amount))
    except (InvalidOperation, TypeError, ValueError):
        amount = Decimal('0.00')
    return f"${amount:,.2f}"


def make_absolute_url(url):
    if not url:
        return ''

    url = str(url)

    if url.startswith(('http://', 'https://')):
        return url

    base = str(getattr(settings, 'BACKEND_URL', '')).rstrip('/')
    if not base:
        return url

    return urljoin(base + '/', url.lstrip('/'))


def get_client_ip(request):
    if not request:
        return ''

    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()

    return request.META.get('REMOTE_ADDR', '')


def split_address_parts(address):
    return [
        part.strip()
        for part in ADDRESS_SEPARATORS.split(str(address or ''))
        if part.strip()
    ]


def is_valid_email(value):
    try:
        validate_email(value)
    except ValidationError:
        return False

    return True


def split_address_contact(address):
    parts = split_address_parts(address)

    for index in range(len(parts) - 1, -1, -1):
        if is_valid_email(parts[index]):
            return parts[:index], parts[index], ', '.join(parts[index + 1:])

    return parts, '', ''


def get_address_contact(*addresses):
    for address in addresses:
        _, email, phone = split_address_contact(address)

        if email:
            return email, phone

    return '', ''


def split_storefront_address(parts):
    country, first_name, last_name, *rest = parts
    zip_code, city = rest[-2:]

    return {
        'name': f'{first_name} {last_name}',
        'line_1': ', '.join(rest[:-2]),
        'line_2': f'{zip_code} {city}',
        'line_3': '',
        'country': country,
    }


def split_address(address):
    data = {
        'name': '',
        'line_1': '',
        'line_2': '',
        'line_3': '',
        'country': '',
    }

    if not address:
        return data

    parts, email, phone = split_address_contact(address)

    if email and phone and len(parts) >= STOREFRONT_ADDRESS_MIN_PARTS:
        return split_storefront_address(parts)

    if not parts:
        return data

    if len(parts) == 1:
        data['line_1'] = parts[0]
        return data

    data['name'] = parts[0]

    if len(parts) == 2:
        data['line_1'] = parts[1]
        return data

    data['country'] = parts[-1]
    body = parts[1:-1]

    if len(body) >= 1:
        data['line_1'] = body[0]

    if len(body) >= 2:
        data['line_2'] = body[1]

    if len(body) >= 3:
        data['line_3'] = ', '.join(body[2:])

    return data


def get_product_image_url(product):
    try:
        images = list(product.images.all())
    except Exception:
        logger.exception(
            'Failed to load product images for product %s',
            getattr(product, 'id', None)
        )
        return PRODUCT_IMAGE_PLACEHOLDER

    if not images:
        return PRODUCT_IMAGE_PLACEHOLDER

    image = images[0]
    url = (
            image.url_original
            or image.url_lg
            or image.url_md
            or image.url_sm
    )

    return make_absolute_url(url) or PRODUCT_IMAGE_PLACEHOLDER


def get_guest_contact(order, guest_cart_token=None):
    address_email, address_phone = get_address_contact(order.shipping_address, order.billing_address)

    if order.user_id and order.user:
        return order.user.email, address_phone or None

    email = None
    phone = None

    if guest_cart_token:
        try:
            from cart.infrastructure.models import GuestCart

            guest_cart = GuestCart.objects.filter(token=guest_cart_token).first()
            session = None

            if guest_cart:
                session = (
                    guest_cart.checkout_sessions
                    .exclude(email__isnull=True)
                    .exclude(email='')
                    .order_by('-created_at')
                    .first()
                )

                if not session:
                    session = guest_cart.checkout_sessions.order_by('-created_at').first()

            if session:
                email = session.email
                phone = session.phone

        except Exception:
            logger.exception(
                'Failed to resolve guest contact for order %s',
                getattr(order, 'id', None)
            )

    return email or address_email or None, phone or address_phone or None


def build_order_context(
        order,
        request=None,
        guest_cart_token=None,
        customer_email=None,
        customer_phone=None,
        ip_address=None,
):
    request_data = getattr(request, 'data', None)

    if request_data and hasattr(request_data, 'get'):
        guest_cart_token = (
                guest_cart_token
                or request_data.get('guest_cart_token')
                or request_data.get('guestCartToken')
        )
        customer_email = customer_email or request_data.get('email')
        customer_phone = customer_phone or request_data.get('phone')

    resolved_email, resolved_phone = get_guest_contact(order, guest_cart_token)

    customer_email = (customer_email or resolved_email or '').strip().lower()
    customer_phone = (customer_phone or resolved_phone or '').strip()

    if order.user_id and order.user:
        customer_email = customer_email or order.user.email

    if not ip_address:
        ip_address = get_client_ip(request)

    ip_address = (ip_address or 'Unknown').strip()

    billing = split_address(order.billing_address)
    shipping = split_address(order.shipping_address)

    fallback_name = ''

    if order.user_id and order.user:
        fallback_name = order.user.get_full_name()

    if not fallback_name and customer_email:
        fallback_name = (
            customer_email
            .split('@')[0]
            .replace('.', ' ')
            .replace('_', ' ')
            .title()
        )

    if not fallback_name:
        fallback_name = 'Customer'

    if not billing['name']:
        billing['name'] = fallback_name

    if not shipping['name']:
        shipping['name'] = fallback_name

    if not billing['country'] and shipping['country']:
        billing['country'] = shipping['country']

    if not shipping['country'] and billing['country']:
        shipping['country'] = billing['country']

    frontend_url = str(getattr(settings, 'FRONTEND_URL', '')).rstrip('/')
    backend_url = str(getattr(settings, "BACKEND_URL", "")).rstrip("/")

    default_view_order_template = f"{frontend_url}/profile"
    default_cancel_order_template = f"{backend_url}/api/orders/{{order_id}}/cancel/?token={{token}}"
    default_product_template = f"{frontend_url}/product/{{product_id}}"

    view_order_template = (
            getattr(settings, 'ORDER_EMAIL_VIEW_ORDER_URL_TEMPLATE', '')
            or default_view_order_template
    )
    cancel_order_template = (
            getattr(settings, 'ORDER_EMAIL_CANCEL_ORDER_URL_TEMPLATE', '')
            or default_cancel_order_template
    )
    product_url_template = (
            getattr(settings, 'ORDER_EMAIL_PRODUCT_URL_TEMPLATE', '')
            or default_product_template
    )

    view_order_link = str(view_order_template).format(order_id=order.id)
    cancel_order_link = str(cancel_order_template).format(order_id=order.id, token=make_cancel_token(order))

    items = []
    order_items = (
        order.items
        .select_related('product', 'product__brand')
        .prefetch_related('product__images')
    )

    for number, item in enumerate(order_items, start=1):
        product = item.product

        product_url = str(product_url_template).format(product_id=product.id)

        sku = (
                getattr(product, 'sku', '')
                or product.slug
                or str(product.id)
        )

        publisher = product.brand.name if getattr(product, 'brand', None) else ''

        items.append({
            'number': number,
            'name': product.name,
            'url': product_url,
            'image_url': get_product_image_url(product),
            'publisher': publisher,
            'sku': sku,
            'quantity': item.quantity,
            'price': format_money(item.price),
            'total': format_money(item.subtotal),
        })

    context = {
        'logo_icon_url': make_absolute_url(
            getattr(settings, 'ORDER_EMAIL_LOGO_ICON_URL', '')
            or LOGO_ICON_PLACEHOLDER
        ),
        'logo_image_url': make_absolute_url(
            getattr(settings, 'ORDER_EMAIL_LOGO_IMAGE_URL', '')
            or LOGO_IMAGE_PLACEHOLDER
        ),
        'cancel_icon_url': make_absolute_url(
            getattr(settings, 'ORDER_EMAIL_CANCEL_ICON_URL', '')
            or CANCEL_ICON_PLACEHOLDER
        ),

        'order_number': str(order.id),
        'order_link': view_order_link,
        'view_order_link': view_order_link,
        'order_date': date_format(
            timezone.localtime(order.created_at),
            'DATETIME_FORMAT'
        ),
        'order_status': ORDER_STATUS_LABELS.get(order.status, order.status),

        'customer_email': customer_email,
        'customer_phone': customer_phone,
        'ip_address': ip_address,

        'payment_method': (
            order.payment_method.name
            if order.payment_method
            else 'Credit Card'
        ),
        'shipping_method': (
            order.delivery_option.name
            if order.delivery_option
            else 'Standard'
        ),

        'billing_name': billing['name'],
        'billing_line_1': billing['line_1'],
        'billing_line_2': billing['line_2'],
        'billing_line_3': billing['line_3'],
        'billing_country': billing['country'],

        'shipping_name': shipping['name'],
        'shipping_line_1': shipping['line_1'],
        'shipping_line_2': shipping['line_2'],
        'shipping_line_3': shipping['line_3'],
        'shipping_country': shipping['country'],

        'items': items,

        'subtotal': format_money(order.subtotal),
        'shipping_cost': format_money(order.shipping_cost),
        'order_total': format_money(order.total_amount),

        'cancel_order_link': cancel_order_link,
    }

    return context


def build_plain_text_content(context):
    lines = [
        'Thank you for your order!',
        '',
        f"Order number: {context['order_number']}",
        f"Order date: {context['order_date']}",
        f"Order status: {context['order_status']}",
        '',
        f"Payment method: {context['payment_method']}",
        f"Shipping method: {context['shipping_method']}",
        '',
        'Items:',
    ]

    for item in context['items']:
        lines.append(
            f"{item['number']}. {item['name']} — "
            f"{item['quantity']} × {item['price']} = {item['total']}"
        )

    lines.extend([
        '',
        f"Subtotal: {context['subtotal']}",
        f"Shipping: {context['shipping_cost']}",
        f"Total: {context['order_total']}",
        '',
        f"View order: {context['view_order_link']}",
        f"Cancel order: {context['cancel_order_link']}",
    ])

    return '\n'.join(lines)


def send_order_confirmation_email(
        order,
        request=None,
        guest_cart_token=None,
        customer_email=None,
        customer_phone=None,
        ip_address=None,
):
    try:
        context = build_order_context(
            order=order,
            request=request,
            guest_cart_token=guest_cart_token,
            customer_email=customer_email,
            customer_phone=customer_phone,
            ip_address=ip_address,
        )

        to_email = context['customer_email']

        if not to_email:
            logger.warning(
                'Order confirmation email was not sent for order %s: '
                'recipient email is empty.',
                order.id
            )
            return False

        html_content = render_to_string('order-email.html', context)
        text_content = build_plain_text_content(context)

        subject = f"Order Confirmation #{context['order_number']}"

        reply_to = (
            [settings.REPLY_TO_EMAIL]
            if getattr(settings, 'REPLY_TO_EMAIL', None)
            else None
        )

        message = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to_email],
            reply_to=reply_to,
        )

        message.attach_alternative(html_content, 'text/html')
        message.send(fail_silently=False)

        logger.info(
            'Order confirmation email sent for order %s to %s',
            order.id,
            to_email
        )

        return True

    except Exception:
        logger.exception(
            'Failed to send order confirmation email for order %s',
            getattr(order, 'id', None)
        )
        return False
