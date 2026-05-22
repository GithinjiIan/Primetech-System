"""
Notification model for in-app and email notifications.
"""
from datetime import timedelta

from django.db import models
from django.conf import settings
from django.utils import timezone


class NotificationQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_archived=False)

    def archived(self):
        return self.filter(is_archived=True)

    def older_than(self, days):
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(created_at__lt=cutoff)

    def archive_old(self, days=30):
        now = timezone.now()
        return self.filter(is_archived=False, created_at__lt=now - timedelta(days=days)).update(
            is_archived=True,
            archived_at=now,
        )


class NotificationManager(models.Manager):
    def get_queryset(self):
        return NotificationQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def archived(self):
        return self.get_queryset().archived()

    def older_than(self, days):
        return self.get_queryset().older_than(days)

    def archive_old(self, days=30):
        return self.get_queryset().archive_old(days)


class Notification(models.Model):
    """In-app notification record for all user types."""

    TYPE_CHOICES = [
        ('enrollment', 'Enrollment'),
        ('application', 'Application'),
        ('course', 'Course Update'),
        ('system', 'System'),
        ('password', 'Password'),
        ('welcome', 'Welcome'),
    ]

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='system', db_index=True)
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False, db_index=True)
    is_archived = models.BooleanField(default=False, db_index=True)
    email_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    objects = NotificationManager()

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'

    def __str__(self):
        return f"[{self.notification_type}] {self.title} → {self.recipient.email}"

    def mark_as_read(self):
        """Mark notification as read and invalidate cache."""
        from django.utils import timezone
        from django.core.cache import cache
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
            # Invalidate cached unread count
            cache.delete(f'unread_notif_count_{self.recipient_id}')


