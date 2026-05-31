"""
Django admin configuration for User management.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth import get_user_model

User = get_user_model()


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom admin for User model with email-based auth."""

    model = User
    list_display = ('email', 'first_name', 'last_name', 'role', 'is_active', 'date_joined')
    list_filter = ('role', 'is_active', 'is_staff', 'gender')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('-date_joined',)

    # Fields shown on the CHANGE form
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': (
            'first_name', 'last_name', 'phone_number',
            'nationality', 'gender', 'profile_picture', 'bio',
        )}),
        ('Role & Permissions', {'fields': (
            'role', 'is_active', 'is_staff', 'is_superuser',
            'must_change_password', 'email_verified',
        )}),
        ('Groups', {'fields': ('groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    # Fields shown on the ADD form
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email', 'first_name', 'last_name', 'role',
                'phone_number', 'gender',
                'password1', 'password2',
                'is_active', 'is_staff', 'must_change_password',
            ),
        }),
    )

    def save_model(self, request, obj, form, change):
        """Keep is_staff in sync with the user's current role."""
        obj.is_staff = obj.role in ('staff', 'superadmin')
        super().save_model(request, obj, form, change)
