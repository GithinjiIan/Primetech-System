"""
Authentication views: login, logout, password change, dashboards.
"""
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, update_session_auth_hash, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.cache import never_cache

from .forms import LoginForm, ForcePasswordChangeForm, ForgotPasswordForm
from .decorators import student_required, staff_required
from .tokens import email_verification_token

User = get_user_model()


# ── helpers ──────────────────────────────────────────────────────
def _redirect_to_dashboard(user):
    """Return the correct dashboard URL for a user's role."""
    if user.role == 'staff':
        return redirect('accounts:staff_dashboard')
    elif user.role == 'superadmin':
        return redirect('admin:index')
    return redirect('accounts:student_dashboard')


# ── auth views ───────────────────────────────────────────────────
@never_cache
@require_http_methods(['GET', 'POST'])
def login_view(request):
    """Handle user login."""
    if request.user.is_authenticated:
        if request.user.must_change_password:
            return redirect('accounts:force_password_change')
        return _redirect_to_dashboard(request.user)

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            # Set session expiry: 0 = browser close, otherwise 2 weeks
            if not form.cleaned_data.get('remember_me'):
                request.session.set_expiry(0)
            else:
                request.session.set_expiry(1209600)  # 2 weeks
            login(request, user)

            if user.must_change_password:
                return redirect('accounts:force_password_change')

            messages.success(request, f'Welcome back, {user.first_name}!')
            return _redirect_to_dashboard(user)
        else:
            messages.error(request, 'Invalid email or password.')
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {'form': form})


@require_POST
def logout_view(request):
    """Log out the current user. POST-only to prevent CSRF logout attacks."""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('accounts:login')


# ── password management ─────────────────────────────────────────
@login_required(login_url='accounts:login')
@never_cache
def force_password_change(request):
    """Force user to set a new password (used after admin-created accounts)."""
    if not request.user.must_change_password:
        return _redirect_to_dashboard(request.user)

    if request.method == 'POST':
        form = ForcePasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            user.must_change_password = False
            user.save(update_fields=['must_change_password'])
            # Prevent session fixation — keep user logged in after password change
            update_session_auth_hash(request, user)
            messages.success(request, 'Password updated successfully! Welcome to PrimeTech LMS.')

            from notifications.utils import create_notification
            create_notification(
                recipient=user,
                notification_type='system',
                title='Password Changed',
                message='Your password has been changed successfully.',
            )
            return _redirect_to_dashboard(user)
    else:
        form = ForcePasswordChangeForm(request.user)

    return render(request, 'accounts/force_password_change.html', {'form': form})


def forgot_password_view(request):
    """Handle forgot-password requests."""
    if request.method == 'POST':
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            try:
                user = User.objects.get(email=email)
                from notifications.tasks import send_password_reset_email
                send_password_reset_email.delay(user.id)
            except User.DoesNotExist:
                pass  # Don't reveal whether the email exists
            messages.success(
                request,
                'If an account exists with that email, a password reset link has been sent.'
            )
            return redirect('accounts:forgot_password')
    else:
        form = ForgotPasswordForm()

    return render(request, 'accounts/forgotpassword.html', {'form': form})


def password_reset_confirm_view(request, uidb64, token):
    """Validate token and allow user to set a new password."""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and email_verification_token.check_token(user, token):
        if request.method == 'POST':
            form = ForcePasswordChangeForm(user, request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, 'Password reset successful. Please log in.')
                return redirect('accounts:login')
        else:
            form = ForcePasswordChangeForm(user)
        return render(request, 'accounts/password_reset_confirm.html', {
            'form': form, 'validlink': True,
        })
    else:
        return render(request, 'accounts/password_reset_confirm.html', {
            'validlink': False,
        })


# ── email verification ──────────────────────────────────────────
def verify_email(request, uidb64, token):
    """Verify user email from the link sent via email."""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user and email_verification_token.check_token(user, token):
        if not user.email_verified:  # Idempotent — only update if needed
            user.email_verified = True
            user.save(update_fields=['email_verified'])
        messages.success(request, 'Email verified successfully!')
        return redirect('accounts:login')
    else:
        messages.error(request, 'Verification link is invalid or has expired.')
        return redirect('accounts:login')


# ── dashboard views ─────────────────────────────────────────────
@student_required
def student_dashboard(request):
    """Student dashboard: shows enrolled courses and notifications."""
    from website.models import Enrollment
    from notifications.models import Notification

    enrollments = Enrollment.objects.filter(
        student=request.user
    ).select_related('course', 'course__category')

    notifications = Notification.objects.filter(
        recipient=request.user
    ).order_by('-created_at')[:10]

    return render(request, 'students/dashboard.html', {
        'enrollments': enrollments,
        'notifications': notifications,
    })


@staff_required
def staff_dashboard(request):
    """Staff/instructor dashboard: shows assigned courses and students."""
    from website.models import Course, Enrollment
    from notifications.models import Notification

    courses = Course.objects.filter(
        assigned_instructor=request.user, is_active=True
    )
    enrollments = Enrollment.objects.filter(
        course__assigned_instructor=request.user
    ).select_related('student', 'course')

    notifications = Notification.objects.filter(
        recipient=request.user
    ).order_by('-created_at')[:10]

    return render(request, 'staff/dashboard.html', {
        'courses': courses,
        'enrollments': enrollments,
        'notifications': notifications,
    })
