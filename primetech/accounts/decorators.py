"""
Role-based access control decorators for views.
"""
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def role_required(allowed_roles):
    """Decorator to restrict view access to specific user roles."""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.warning(request, 'Please log in to access this page.')
                return redirect('accounts:login')
            if request.user.role not in allowed_roles:
                messages.error(request, 'You do not have permission to access this page.')
                return redirect('accounts:login')
            # Force password change redirect
            if request.user.must_change_password:
                return redirect('accounts:force_password_change')
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def student_required(view_func):
    """Allow only students."""
    return role_required(['student'])(view_func)


def staff_required(view_func):
    """Allow only staff/instructors."""
    return role_required(['staff'])(view_func)


def superadmin_required(view_func):
    """Allow only super admins."""
    return role_required(['superadmin'])(view_func)


def staff_or_admin_required(view_func):
    """Allow staff or super admins."""
    return role_required(['staff', 'superadmin'])(view_func)
