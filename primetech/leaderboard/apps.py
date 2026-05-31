"""
AppConfig for the leaderboard gamification app.
Wires signals on startup.
"""

from django.apps import AppConfig


class LeaderboardConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'leaderboard'
    verbose_name       = 'Gamification & Leaderboard'

    def ready(self):
        # Import signals module so receivers are registered
        import leaderboard.signals  # noqa: F401
