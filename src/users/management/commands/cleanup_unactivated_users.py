import logging
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from users.infrastructure.models import User

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Видаляє неактивовані акаунти, старіші за 3 дні'

    def handle(self, *args, **kwargs):
        ttl_days = getattr(settings, 'ACTIVATION_ACCOUNT_TTL_DAYS', 3)
        threshold = timezone.now() - timedelta(days=ttl_days)

        users_to_delete = User.objects.filter(
            is_active=False,
            date_joined__lt=threshold,
        )
        count = users_to_delete.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS('Неактивованих акаунтів не знайдено.'))
            return

        users_to_delete.delete()
        self.stdout.write(self.style.SUCCESS(f'Видалено {count} неактивованих акаунтів.'))
        logger.info(f"Cleanup: видалено {count} акаунтів, старіших за {ttl_days} дні.")
