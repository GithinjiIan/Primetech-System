"""
Celery tasks for sending emails asynchronously.
"""
import logging

from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_welcome_email(self, user_id, temp_password):
    """Send congratulatory enrollment email with temporary login credentials."""
    from django.contrib.auth import get_user_model
    User = get_user_model()

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.error('send_welcome_email: User %s not found, skipping.', user_id)
        return  # Don't retry — user was deleted

    try:
        subject = 'Congratulations! Welcome to PrimeTech LMS'
        html_message = render_to_string('emails/welcome.html', {
            'user': user,
            'temp_password': temp_password,
            'login_url': settings.SITE_URL + '/accounts/login/',
        })
        plain_message = strip_tags(html_message)

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )

        from notifications.models import Notification
        Notification.objects.filter(
            recipient=user, notification_type='welcome'
        ).update(email_sent=True)
        logger.info('Welcome email sent to %s', user.email)

    except Exception as exc:
        logger.warning('send_welcome_email failed for %s: %s', user.email, exc)
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_password_reset_email(self, user_id):
    """Send password reset email with a secure token link."""
    from django.contrib.auth import get_user_model
    from accounts.tokens import email_verification_token
    User = get_user_model()

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.error('send_password_reset_email: User %s not found.', user_id)
        return

    try:
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = email_verification_token.make_token(user)
        reset_url = f"{settings.SITE_URL}/accounts/password/reset/{uid}/{token}/"

        subject = 'PrimeTech LMS — Password Reset'
        html_message = render_to_string('emails/password_reset.html', {
            'user': user,
            'reset_url': reset_url,
        })
        plain_message = strip_tags(html_message)

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info('Password reset email sent to %s', user.email)
    except Exception as exc:
        logger.warning('send_password_reset_email failed for %s: %s', user.email, exc)
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_application_status_email(self, application_id, status):
    """Notify applicant about their application status."""
    from website.models import CourseApplication

    try:
        application = CourseApplication.objects.select_related('course').get(pk=application_id)
    except CourseApplication.DoesNotExist:
        logger.error('send_application_status_email: Application %s not found.', application_id)
        return

    try:
        subject = f'PrimeTech LMS — Application {status.title()}'
        html_message = render_to_string('emails/application_status.html', {
            'application': application,
            'status': status,
        })
        plain_message = strip_tags(html_message)

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[application.email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info('Application status email (%s) sent to %s', status, application.email)
    except Exception as exc:
        logger.warning('send_application_status_email failed: %s', exc)
        raise self.retry(exc=exc, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_notification_email(self, notification_id):
    """Send a generic notification email."""
    from notifications.models import Notification

    try:
        notification = Notification.objects.select_related('recipient').get(pk=notification_id)
    except Notification.DoesNotExist:
        logger.error('send_notification_email: Notification %s not found.', notification_id)
        return

    try:
        subject = f'PrimeTech LMS — {notification.title}'
        html_message = render_to_string('emails/notification.html', {
            'notification': notification,
            'user': notification.recipient,
        })
        plain_message = strip_tags(html_message)

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[notification.recipient.email],
            html_message=html_message,
            fail_silently=False,
        )
        notification.email_sent = True
        notification.save(update_fields=['email_sent'])
        logger.info('Notification email sent: %s -> %s', notification.title, notification.recipient.email)

    except Exception as exc:
        logger.warning('send_notification_email failed for notification %s: %s', notification_id, exc)
        raise self.retry(exc=exc, countdown=60)
