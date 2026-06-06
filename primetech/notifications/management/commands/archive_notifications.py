from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from notifications.models import Notification


class Command(BaseCommand):
    help = 'Archive notifications older than the configured number of days.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=14,
            help='Archive notifications older than this many days.',
        )

    def handle(self, *args, **options):
        days = options['days']
        cutoff = timezone.now() - timedelta(days=days)
        archived_count = Notification.objects.filter(
            is_archived=False,
            created_at__lt=cutoff,
        ).update(
            is_archived=True,
            archived_at=timezone.now(),
        )

        self.stdout.write(self.style.SUCCESS(
            f'Archived {archived_count} notifications older than {days} days.'
        ))
