"""
Views for notification management (mark read, list).
"""
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Notification


@login_required(login_url='accounts:login')
@require_POST
def mark_as_read(request, pk):
    """Mark a single notification as read."""
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.mark_as_read()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'ok'})
    return redirect(request.META.get('HTTP_REFERER', '/'))


@login_required(login_url='accounts:login')
@require_POST
def mark_all_read(request):
    """Mark all notifications for the current user as read."""
    from django.utils import timezone
    Notification.objects.filter(
        recipient=request.user, is_read=False
    ).update(is_read=True, read_at=timezone.now())
    # Invalidate cached count
    cache.delete(f'unread_notif_count_{request.user.pk}')
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'ok'})
    return redirect(request.META.get('HTTP_REFERER', '/'))


