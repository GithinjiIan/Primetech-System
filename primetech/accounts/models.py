"""
Custom User model with role-based access for PrimeTech LMS.
Roles: student, staff (instructor), superadmin.
"""
from django.contrib.auth.models import AbstractUser
from django.db import models
from .managers import CustomUserManager


class User(AbstractUser):
    """Custom user model using email as the primary identifier."""

    ROLE_CHOICES = [
        ('student', 'Student'),
        ('staff', 'Staff / Instructor'),
        ('superadmin', 'Super Admin'),
    ]
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
    ]

    # Remove username field — email is the login identifier
    username = None
    email = models.EmailField('email address', unique=True)

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    phone_number = models.CharField(max_length=20, blank=True)
    nationality = models.CharField(max_length=100, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)

    # Password management
    must_change_password = models.BooleanField(
        default=False,
        help_text='Force user to change password on next login.'
    )
    email_verified = models.BooleanField(default=False)

    # Profile
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
    bio = models.TextField(blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    objects = CustomUserManager()

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-date_joined']

    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"

    @property
    def is_student(self):
        return self.role == 'student'

    @property
    def is_instructor(self):
        return self.role == 'staff'

    @property
    def is_superadmin(self):
        return self.role == 'superadmin'
