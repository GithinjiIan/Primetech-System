"""
Celery tasks for the leaderboard / gamification app.

Beat schedule (configured in settings.py):
  - reset_streaks_midnight        : 00:00 Africa/Nairobi daily
  - generate_daily_challenges     : 01:00 Africa/Nairobi daily
  - award_top3_leaderboard_badges : 02:00 Africa/Nairobi daily
  - check_milestone_badges        : 02:30 Africa/Nairobi daily
"""

import logging
import random
from datetime import timedelta

from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import DailyChallenge, Badge
from . import services

User = get_user_model()
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────
# Streak reset — runs at midnight Africa/Nairobi
# ─────────────────────────────────────────────────────────────────

@shared_task(bind=True, name='leaderboard.reset_streaks_midnight')
def reset_streaks_midnight(self):
    """
    For every active student, check whether they maintained their
    streak yesterday.  If not, consume a freeze or reset to zero.
    """
    students = User.objects.filter(role='student', is_active=True)
    count = 0
    for student in students:
        try:
            services.process_midnight_streak_reset(student)
            count += 1
        except Exception as exc:
            logger.error("Streak reset failed for user %s: %s", student.pk, exc)
    logger.info("Streak reset completed for %s students.", count)
    return f"Processed {count} students."


# ─────────────────────────────────────────────────────────────────
# Daily challenge generation — runs at 01:00 Africa/Nairobi
# ─────────────────────────────────────────────────────────────────

CHALLENGE_TEMPLATES = [
    {
        'title':          'Material Sprint 📚',
        'description':    'Complete {n} course materials today to prove your dedication!',
        'challenge_type': 'complete_materials',
        'target_count':   3,
        'xp_reward':      100,
        'reward_type':    'xp',
    },
    {
        'title':          'Assignment Warrior ⚔️',
        'description':    'Submit {n} assignments today and stay ahead of the curve.',
        'challenge_type': 'submit_assignments',
        'target_count':   1,
        'xp_reward':      120,
        'reward_type':    'xp_freeze',
    },
    {
        'title':          'Deep Focus Session 🎯',
        'description':    'Stay active on the platform for at least {n} minutes today.',
        'challenge_type': 'active_minutes',
        'target_count':   45,
        'xp_reward':      80,
        'reward_type':    'xp',
    },
    {
        'title':          'XP Grinder ⚡',
        'description':    'Earn {n} XP today through any activity.',
        'challenge_type': 'earn_xp',
        'target_count':   150,
        'xp_reward':      100,
        'reward_type':    'xp_freeze',
    },
    {
        'title':          'Learning Marathon 🏃',
        'description':    'Complete {n} materials without stopping. Consistency is key!',
        'challenge_type': 'complete_materials',
        'target_count':   5,
        'xp_reward':      150,
        'reward_type':    'xp',
    },
]


@shared_task(bind=True, name='leaderboard.generate_daily_challenges')
def generate_daily_challenges(self):
    """
    Auto-generate 3 daily challenges for today if none exist yet.
    Skips dates that already have auto-generated challenges.
    """
    today = timezone.localdate()
    existing = DailyChallenge.objects.filter(date=today, is_auto_generated=True).count()
    if existing != 0:
        logger.info("Daily challenges already exist for %s, skipping.", today)
        return "Already generated."

    templates = random.sample(CHALLENGE_TEMPLATES, k=min(3, len(CHALLENGE_TEMPLATES)))
    created   = 0

    for tmpl in templates:
        n = tmpl['target_count']
        _, was_created = DailyChallenge.objects.get_or_create(
            date=today,
            title=tmpl['title'],
            defaults={
                'description':      tmpl['description'].format(n=n),
                'challenge_type':   tmpl['challenge_type'],
                'target_count':     n,
                'xp_reward':        tmpl['xp_reward'],
                'reward_type':      tmpl['reward_type'],
                'is_auto_generated': True,
            }
        )
        if was_created:
            created += 1

    logger.info("Generated %s daily challenges for %s.", created, today)
    return f"Created {created} challenges."


# ─────────────────────────────────────────────────────────────────
# Top-3 leaderboard badge — runs at 02:00 Africa/Nairobi daily
# ─────────────────────────────────────────────────────────────────

@shared_task(bind=True, name='leaderboard.award_top3_leaderboard_badges')
def award_top3_leaderboard_badges(self):
    """
    Check the current global leaderboard and award the
    'Top 3 on Leaderboard' badge to qualifying students.
    """
    try:
        badge = Badge.objects.get(criteria_type='top3_leaderboard', is_active=True)
    except Badge.DoesNotExist:
        logger.warning("Top-3 badge does not exist yet; skipping.")
        return "Badge not found."

    top3_ids = services.get_top3_user_ids('all_time')
    awarded  = 0
    for user_id in top3_ids:
        try:
            user = User.objects.get(pk=user_id, role='student')
            services.get_or_create_profile(user)
            services.check_and_award_badges(user)
            awarded += 1
        except Exception as exc:
            logger.error("Top-3 badge award failed for user %s: %s", user_id, exc)

    logger.info("Top-3 badge awarded to %s students.", awarded)
    return f"Awarded to {awarded} students."


# ─────────────────────────────────────────────────────────────────
# Milestone badge sweep — runs at 02:30 Africa/Nairobi daily
# ─────────────────────────────────────────────────────────────────

@shared_task(bind=True, name='leaderboard.check_milestone_badges')
def check_milestone_badges(self):
    """
    Run a full badge check for every active student.
    Catches any badges that signals might have missed (edge cases).
    """
    students = User.objects.filter(role='student', is_active=True)
    count = 0
    for student in students:
        try:
            services.check_and_award_badges(student)
            count += 1
        except Exception as exc:
            logger.error("Badge check failed for user %s: %s", student.pk, exc)
    logger.info("Milestone badge sweep completed for %s students.", count)
    return f"Checked {count} students."
