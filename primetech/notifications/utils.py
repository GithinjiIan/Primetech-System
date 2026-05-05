"""
Utility functions for creating notifications and triggering emails.
"""
from django.core.cache import cache
from .models import Notification


def create_notification(recipient, notification_type, title, message, send_email=True):
    """Create an in-app notification and optionally queue an email."""
    notification = Notification.objects.create(
        recipient=recipient,
        notification_type=notification_type,
        title=title,
        message=message,
    )

    # Invalidate cached unread count for this user
    cache.delete(f'unread_notif_count_{recipient.pk}')

    if send_email:
        from .tasks import send_notification_email
        send_notification_email.delay(notification.id)

    return notification
