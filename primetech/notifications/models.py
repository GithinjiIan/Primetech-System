"""
Notification model for in-app and email notifications.
"""
from django.db import models
from django.conf import settings


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
    email_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

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


