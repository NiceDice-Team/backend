import logging
from datetime import timedelta

from django.core.signing import BadSignature, Signer
from django.db import transaction
from django.utils import timezone

from orders.infrastructure.models import Order, OrderStatusLog

logger = logging.getLogger(__name__)

CANCELLATION_WINDOW_HOURS = 48
CANCELLATION_WINDOW = timedelta(hours=CANCELLATION_WINDOW_HOURS)
CANCELLABLE_STATUSES = ("pending", "processing")
CANCELLED_STATUS = "cancelled"
CANCEL_TOKEN_SALT = "orders.cancel-order-link"


class OrderCancellationError(Exception):
    INVALID_LINK = "invalid_link"
    ALREADY_SHIPPED = "already_shipped"
    WINDOW_EXPIRED = "window_expired"

    def __init__(self, code, order=None):
        super().__init__(code)
        self.code = code
        self.order = order


def _cancel_token_payload(order):
    return f"{order.pk}.{int(order.created_at.timestamp())}"


def make_cancel_token(order):
    return Signer(salt=CANCEL_TOKEN_SALT).signature(_cancel_token_payload(order))


def is_valid_cancel_token(order, token):
    if not token:
        return False
    signer = Signer(salt=CANCEL_TOKEN_SALT)
    payload = _cancel_token_payload(order)
    try:
        return signer.unsign(f"{payload}{signer.sep}{token}") == payload
    except BadSignature:
        return False


def cancel_order_by_token(order_id, token):
    with transaction.atomic():
        order = Order.objects.select_for_update().filter(pk=order_id).first()
        if order is None or not is_valid_cancel_token(order, token):
            raise OrderCancellationError(OrderCancellationError.INVALID_LINK)

        if order.status == CANCELLED_STATUS:
            return order

        if order.status not in CANCELLABLE_STATUSES:
            raise OrderCancellationError(OrderCancellationError.ALREADY_SHIPPED, order)

        if timezone.now() > order.created_at + CANCELLATION_WINDOW:
            raise OrderCancellationError(OrderCancellationError.WINDOW_EXPIRED, order)

        previous_status = order.status
        order.status = CANCELLED_STATUS
        order.save(update_fields=["status", "updated_at"])

        OrderStatusLog.objects.create(
            order=order,
            previous_status=previous_status,
            new_status=CANCELLED_STATUS,
            changed_by=order.user,
        )

    logger.info("Order %s was cancelled by the customer via the email link", order.pk)
    return order
