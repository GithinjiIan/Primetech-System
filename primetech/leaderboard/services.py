"""
Gamification service layer for PrimeTech LMS.

All XP grants, streak updates, badge checks, and leaderboard
queries go through this module so views and signals stay thin.
"""

import logging
from datetime import timedelta

from django.utils import timezone
from django.db import transaction
from django.db.models import Sum, Count, Q
from django.contrib.auth import get_user_model

from .models import (
    GamificationProfile,
    Badge,
    UserBadge,
    XPTransaction,
    ActivitySession,
    ChallengeCompletion,
    DailyChallenge,
    XP_MATERIAL_COMPLETE,
    XP_ASSIGNMENT_SUBMIT,
    XP_GRADE_HIGH,
    XP_GRADE_MID,
    XP_CHALLENGE_COMPLETE,
    XP_BADGE_EARNED,
    STREAK_MIN_TASKS,
    STREAK_MIN_MINUTES,
)

User = get_user_model()
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────
# Profile helpers
# ─────────────────────────────────────────────────────────────────

def get_or_create_profile(user) -> GamificationProfile:
    """Return (or lazily create) a student's GamificationProfile."""
    profile, _ = GamificationProfile.objects.get_or_create(user=user)
    return profile


# ─────────────────────────────────────────────────────────────────
# XP
# ─────────────────────────────────────────────────────────────────

@transaction.atomic
def award_xp(user, amount: int, reason: str, description: str = '', material_id=None) -> GamificationProfile:
    """
    Grant `amount` XP to `user`, log the transaction, and return
    the updated GamificationProfile.

    `reason` must be one of XPTransaction.REASON_CHOICES keys.
    """
    if amount == 0:
        return get_or_create_profile(user)

    profile = GamificationProfile.objects.select_for_update().get_or_create(user=user)[0]

    if material_id is not None:
        txn, created = XPTransaction.objects.get_or_create(
            user=user,
            reason=reason,
            material_id=material_id,
            defaults={
                'xp_amount': amount,
                'description': description,
            }
        )
        if not created:
            profile._xp_awarded = False
            return profile

    previous = profile.total_xp
    new_total = max(0, previous + amount)
    applied_delta = new_total - previous
    profile.total_xp = new_total
    profile.save(update_fields=['total_xp', 'updated_at'])

    if material_id is None:
        XPTransaction.objects.create(
            user=user,
            xp_amount=applied_delta,
            reason=reason,
            description=description,
        )
    else:
        # Update the stored transaction amount to match the actually applied delta.
        txn.xp_amount = applied_delta
        txn.description = description
        txn.save(update_fields=['xp_amount', 'description'])

    profile._xp_awarded = True
    logger.info("XP awarded: user=%s amount=%s reason=%s", user.pk, applied_delta, reason)
    return profile


# ─────────────────────────────────────────────────────────────────
# Streak management
# ─────────────────────────────────────────────────────────────────

@transaction.atomic
def record_task_completion(user) -> GamificationProfile:
    """
    Increment the daily task counter for `user` and check whether
    the streak threshold has been met (2 tasks + 30 minutes).
    Call this whenever a material is completed or an assignment submitted.
    """
    profile = GamificationProfile.objects.select_for_update().get_or_create(user=user)[0]
    today   = timezone.localdate()

    # Reset daily counter if it's a new day
    if profile.last_activity_date != today:
        profile.tasks_today = 0

    profile.tasks_today += 1
    profile.save(update_fields=['tasks_today', 'updated_at'])

    # Check streak threshold
    _maybe_advance_streak(profile, today)
    return profile


def _maybe_advance_streak(profile: GamificationProfile, today):
    """Advance the streak if today's tasks + activity-time thresholds are met."""
    if profile.last_activity_date == today:
        # Streak already updated today
        return

    minutes_today = _get_active_minutes_today(profile.user, today)

    if profile.tasks_today >= STREAK_MIN_TASKS and minutes_today >= STREAK_MIN_MINUTES:
        yesterday = today - timedelta(days=1)
        if profile.last_activity_date == yesterday or profile.last_activity_date is None:
            profile.current_streak += 1
        else:
            # Gap detected; streak starts fresh
            profile.current_streak = 1

        profile.longest_streak   = max(profile.longest_streak, profile.current_streak)
        profile.last_activity_date = today
        profile.save(update_fields=['current_streak', 'longest_streak', 'last_activity_date', 'updated_at'])

        logger.info("Streak advanced: user=%s streak=%s", profile.user_id, profile.current_streak)

        # Check streak-milestone badges
        check_and_award_badges(profile.user)


def _get_active_minutes_today(user, today) -> int:
    """Return total active minutes logged for `user` today via ActivitySession."""
    result = ActivitySession.objects.filter(
        user=user, session_date=today
    ).aggregate(total=Sum('duration_seconds'))
    return (result['total'] or 0) // 60


@transaction.atomic
def process_midnight_streak_reset(user) -> None:
    """
    Called by the Celery midnight task for each student.
    If the student did NOT log a qualifying day yesterday:
      - Consume a freeze (if available), OR
      - Reset streak to 0.
    Also resets the daily task counter.
    """
    profile = GamificationProfile.objects.select_for_update().get_or_create(user=user)[0]
    today     = timezone.localdate()
    yesterday = today - timedelta(days=1)

    # Reset daily counters regardless
    profile.tasks_today = 0

    if profile.last_activity_date != yesterday:
        # Streak was not maintained yesterday
        if profile.freeze_count > 0:
            profile.freeze_count -= 1
            logger.info("Streak freeze consumed: user=%s freezes_remaining=%s", user.pk, profile.freeze_count)
        else:
            profile.current_streak = 0
            logger.info("Streak reset: user=%s", user.pk)

    profile.save(update_fields=['tasks_today', 'freeze_count', 'current_streak', 'updated_at'])


# ─────────────────────────────────────────────────────────────────
# Badge awards
# ─────────────────────────────────────────────────────────────────

def check_and_award_badges(user) -> list:
    """
    Check all active badge criteria for `user` and award any newly earned.
    Returns list of newly awarded Badge instances.
    """
    profile        = get_or_create_profile(user)
    already_earned = set(UserBadge.objects.filter(user=user).values_list('badge_id', flat=True))
    awarded         = []

    candidates = Badge.objects.filter(is_active=True).exclude(id__in=already_earned)

    for badge in candidates:
        if _criteria_met(badge.criteria_type, user, profile):
            _award_badge(user, badge, profile)
            awarded.append(badge)

    return awarded


def _criteria_met(criteria_type: str, user, profile: GamificationProfile) -> bool:
    """Return True if the badge criteria is currently satisfied."""
    from courses.models import MaterialProgress
    from website.models import Enrollment

    ct = criteria_type
    if ct == 'streak_7':           return profile.current_streak >= 7
    if ct == 'streak_30':          return profile.current_streak >= 30
    if ct == 'streak_100':         return profile.current_streak >= 100
    if ct == 'xp_500':             return profile.total_xp >= 500
    if ct == 'xp_1000':            return profile.total_xp >= 1000
    if ct == 'xp_5000':            return profile.total_xp >= 5000
    if ct == 'first_submit':
        from courses.models import Submission
        return Submission.objects.filter(student=user).exists()
    if ct == 'module_master':
        return MaterialProgress.objects.filter(student=user, completed=True).count() >= 10
    if ct == 'course_complete':
        # Check if any course has 100% completion
        enrollments = Enrollment.objects.filter(student=user, status='active')
        for enr in enrollments:
            total = enr.course.materials.filter(is_published=True).count()
            if total == 0:
                continue
            done = MaterialProgress.objects.filter(
                student=user, material__course=enr.course, completed=True
            ).count()
            if done >= total:
                return True
        return False
    if ct == 'challenge_10':
        return ChallengeCompletion.objects.filter(user=user).count() >= 10
    if ct == 'top3_leaderboard':
        # Checked separately by the nightly Celery task; skip here
        return False
    return False


@transaction.atomic
def _award_badge(user, badge: Badge, profile: GamificationProfile) -> UserBadge:
    """Create UserBadge record and grant bonus XP."""
    ub, created = UserBadge.objects.get_or_create(user=user, badge=badge)
    if created:
        award_xp(user, XP_BADGE_EARNED, 'badge_earned', f'Badge earned: {badge.name}')
        logger.info("Badge awarded: user=%s badge=%s", user.pk, badge.name)
    return ub


# ─────────────────────────────────────────────────────────────────
# Challenge progress
# ─────────────────────────────────────────────────────────────────

def evaluate_challenges_for_user(user) -> None:
    """
    Check today's open challenges and auto-complete any whose threshold
    the user has now crossed.  Called after each qualifying action.
    """
    today      = timezone.localdate()
    challenges = DailyChallenge.objects.filter(date=today)
    done_ids   = set(
        ChallengeCompletion.objects.filter(user=user, challenge__date=today)
        .values_list('challenge_id', flat=True)
    )

    profile = get_or_create_profile(user)

    for ch in challenges:
        if ch.pk in done_ids:
            continue
        if _challenge_threshold_met(ch, user, profile):
            _complete_challenge(user, ch, profile)


def _challenge_threshold_met(ch: DailyChallenge, user, profile: GamificationProfile) -> bool:
    """Return True if the user has crossed the challenge threshold today."""
    today = timezone.localdate()

    if ch.challenge_type == 'complete_materials':
        from courses.models import MaterialProgress
        count = MaterialProgress.objects.filter(
            student=user, completed=True, completed_at__date=today
        ).count()
        return count >= ch.target_count

    if ch.challenge_type == 'submit_assignments':
        from courses.models import Submission
        count = Submission.objects.filter(
            student=user, submitted_at__date=today
        ).count()
        return count >= ch.target_count

    if ch.challenge_type == 'active_minutes':
        return _get_active_minutes_today(user, today) >= ch.target_count

    if ch.challenge_type == 'earn_xp':
        today_xp = XPTransaction.objects.filter(
            user=user, created_at__date=today, xp_amount__gt=0
        ).aggregate(total=Sum('xp_amount'))['total'] or 0
        return today_xp >= ch.target_count

    return False


@transaction.atomic
def _complete_challenge(user, challenge: DailyChallenge, profile: GamificationProfile) -> None:
    """Mark challenge as completed and grant rewards."""
    completion, created = ChallengeCompletion.objects.get_or_create(user=user, challenge=challenge)
    if not created:
        return

    # XP reward
    award_xp(user, challenge.xp_reward, 'challenge_complete', f'Challenge: {challenge.title}')

    # Streak freeze reward
    if challenge.reward_type in ('freeze', 'xp_freeze'):
        p = GamificationProfile.objects.select_for_update().get(user=user)
        p.freeze_count += 1
        p.save(update_fields=['freeze_count', 'updated_at'])

    # Badge reward
    if challenge.reward_type == 'badge' and challenge.badge_reward:
        _award_badge(user, challenge.badge_reward, profile)

    # Check milestones after earning XP
    check_and_award_badges(user)
    logger.info("Challenge completed: user=%s challenge=%s", user.pk, challenge.title)


# ─────────────────────────────────────────────────────────────────
# Leaderboard queries
# ─────────────────────────────────────────────────────────────────

def get_leaderboard(period: str = 'all_time', limit: int = 50):
    """
    Return a queryset of GamificationProfiles ranked by XP for the given period.

    period: 'all_time' | 'monthly' | 'weekly'
    """
    qs = GamificationProfile.objects.filter(
        user__role='student',
        user__is_active=True,
    ).select_related('user')

    if period == 'monthly':
        cutoff = timezone.now() - timedelta(days=30)
        # Use XPTransaction to compute monthly XP
        monthly_xp = (
            XPTransaction.objects
            .filter(user__role='student', created_at__gte=cutoff, xp_amount__gt=0)
            .values('user_id')
            .annotate(period_xp=Sum('xp_amount'))
        )
        # Build a dict for lookup
        xp_map = {row['user_id']: row['period_xp'] for row in monthly_xp}
        profiles = list(qs)
        for p in profiles:
            p.period_xp = xp_map.get(p.user_id, 0)
        profiles.sort(key=lambda p: p.period_xp, reverse=True)
        return profiles[:limit]

    elif period == 'weekly':
        cutoff = timezone.now() - timedelta(days=7)
        weekly_xp = (
            XPTransaction.objects
            .filter(user__role='student', created_at__gte=cutoff, xp_amount__gt=0)
            .values('user_id')
            .annotate(period_xp=Sum('xp_amount'))
        )
        xp_map = {row['user_id']: row['period_xp'] for row in weekly_xp}
        profiles = list(qs)
        for p in profiles:
            p.period_xp = xp_map.get(p.user_id, 0)
        profiles.sort(key=lambda p: p.period_xp, reverse=True)
        return profiles[:limit]

    else:  # all_time
        profiles = list(qs.order_by('-total_xp')[:limit])
        for p in profiles:
            p.period_xp = p.total_xp
        return profiles


def _get_period_cutoff(period: str):
    if period == 'weekly':
        return timezone.now() - timedelta(days=7)
    if period == 'monthly':
        return timezone.now() - timedelta(days=30)
    return None


def _get_user_period_xp(user, period: str) -> int:
    cutoff = _get_period_cutoff(period)
    if cutoff is None:
        return get_or_create_profile(user).total_xp

    return XPTransaction.objects.filter(
        user=user,
        created_at__gte=cutoff,
        xp_amount__gt=0,
    ).aggregate(total=Sum('xp_amount'))['total'] or 0


def get_user_rank(user, period: str = 'all_time') -> int:
    """Return the 1-based rank of `user` in the given period leaderboard."""
    user_xp = _get_user_period_xp(user, period)
    if period == 'all_time':
        return (
            GamificationProfile.objects.filter(
                user__role='student',
                user__is_active=True,
                total_xp__gt=user_xp,
            ).count() + 1
        )

    cutoff = _get_period_cutoff(period)
    higher_users = (
        XPTransaction.objects
        .filter(user__role='student', user__is_active=True, created_at__gte=cutoff, xp_amount__gt=0)
        .values('user_id')
        .annotate(period_xp=Sum('xp_amount'))
        .filter(period_xp__gt=user_xp)
        .count()
    )
    return higher_users + 1


def get_top3_user_ids(period: str = 'all_time') -> list:
    """Return the user PKs of the top-3 students."""
    return [p.user_id for p in get_leaderboard(period, limit=3)]
