"""
Signals for accounts app - triggered on user creation events.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

User = get_user_model()


@receiver(post_save, sender=User)
def notify_admin_on_new_staff(sender, instance, created, **kwargs):
    """Notify admins when a new staff member is created."""
    if created and instance.role == 'staff':
        from notifications.utils import create_notification
        # Notify all superadmins
        admins = User.objects.filter(role='superadmin', is_active=True)
        for admin_user in admins:
            create_notification(
                recipient=admin_user,
                notification_type='system',
                title='New Instructor Added',
                message=f'A new instructor "{instance.get_full_name()}" has been added to the system.',
            )
