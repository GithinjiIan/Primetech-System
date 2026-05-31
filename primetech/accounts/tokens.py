"""
Custom token generators for email verification and password reset.
"""
from django.contrib.auth.tokens import PasswordResetTokenGenerator as DjangoPasswordResetTokenGenerator


class EmailVerificationTokenGenerator(DjangoPasswordResetTokenGenerator):
    """Token generator for email verification links."""

    def _make_hash_value(self, user, timestamp):
        return str(user.pk) + str(timestamp) + str(user.email_verified)


class PasswordResetTokenGenerator(DjangoPasswordResetTokenGenerator):
    """Dedicated token generator for password reset links."""

    def _make_hash_value(self, user, timestamp):
        # Include current password hash so any password change invalidates
        # previously issued tokens immediately.
        return str(user.pk) + str(user.password) + str(timestamp)


email_verification_token = EmailVerificationTokenGenerator()
password_reset_token = PasswordResetTokenGenerator()
