"""
Context processor to inject unread notification count into all templates.
Uses caching to avoid a DB query on every single request.
"""
from django.core.cache import cache


def notification_count(request):
    """Add unread_notifications_count to template context."""
    if request.user.is_authenticated:
        cache_key = f'unread_notif_count_{request.user.pk}'
        count = cache.get(cache_key)
        if count is None:
            count = request.user.notifications.filter(is_read=False).count()
            cache.set(cache_key, count, 60)  # Cache for 60 seconds
        return {'unread_notifications_count': count}
    return {'unread_notifications_count': 0}
