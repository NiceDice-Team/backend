import logging
import threading

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


class RegistrationEmailError(Exception):
    pass


def build_registration_email_body(first_name: str, activation_url: str, subscribe_news: bool) -> str:
    user_name = first_name or "User"

    body = (
        f"Hello {user_name}!\n\n"
        f"Thank you for registering with Dice & Decks.\n\n"
        f"Please click on the link below to activate your account:\n\n"
        f"{activation_url}\n\n"
        f"! The activation link is valid for 1 hour from the moment you receive the email.\n\n"
        f"If you have not registered, please ignore this email.\n\n"
        f"----------------------------------------\n\n"
    )

    if subscribe_news:
        body += (
            "Thank you for subscribing!\n"
            "You will receive updates about our news :\n\n"
        )

    body += "Thank you for choosing Dice & Decks!\n"
    return body


def send_registration_email(email: str, first_name: str, activation_url: str, subscribe_news: bool) -> None:
    subject = "Welcome to Dice & Decks! Please confirm your email"
    body = build_registration_email_body(first_name, activation_url, subscribe_news)

    try:
        sent_count = send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
    except Exception as exc:
        logger.exception("Registration email FAILED to send to %s", email)
        raise RegistrationEmailError(str(exc)) from exc

    if not sent_count:
        logger.warning("Registration email was NOT accepted by email backend for %s", email)
        raise RegistrationEmailError("The email backend did not accept the message.")

    logger.info(
        "Registration email sent successfully to %s (subscribe_news=%s)",
        email,
        subscribe_news,
    )


def send_activation_email_async(email, subscribe_news):
    def _send():
        try:
            message = (
                "Welcome!\n"
                "Your registration was successful.\n"
                "Your account has been activated."
            )
            if subscribe_news:
                message += (
                    "\nYou are also subscribed to our news and special offers. "
                    "You will be the first to know about new arrivals, promotions and discounts."
                )
            send_mail(
                "Account Activation",
                message,
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            logger.info("Activation email sent to %s", email)
        except Exception:
            logger.exception("Activation email failed for %s", email)

    thread = threading.Thread(target=_send, daemon=True)
    thread.start()
    return thread


def send_newsletter_welcome_email_async(email):
    def _send():
        try:
            send_mail(
                "Thank you for subscribing",
                "Thank you for subscribing to our updates.",
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            logger.info("Newsletter welcome email sent to %s", email)
        except Exception:
            logger.exception("Newsletter welcome email failed for %s", email)

    thread = threading.Thread(target=_send, daemon=True)
    thread.start()
    return thread
