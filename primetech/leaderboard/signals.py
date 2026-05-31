"""
Django signals for the leaderboard app.

Intercepts events from courses app models so the gamification
logic never pollutes the courses views.
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from courses.models import MaterialProgress, Submission, Grade
from .models import ChallengeCompletion
from . import services

logger = logging.getLogger(__name__)


# ── Material completed ────────────────────────────────────────────

@receiver(post_save, sender=MaterialProgress)
def on_material_progress_save(sender, instance: MaterialProgress, created, **kwargs):
    """Award XP and record task completion when a material is marked complete."""
    if not instance.completed:
        return
    if not instance.student.is_student:
        return

    # Award XP only once per material completion event.
    profile = services.award_xp(
        user=instance.student,
        amount=services.XP_MATERIAL_COMPLETE,
        reason='material_complete',
        description=f'Completed: {instance.material.title}',
        material_id=instance.material.id,
    )
    if getattr(profile, '_xp_awarded', True) is False:
        return

    # Update streak counter
    services.record_task_completion(instance.student)

    # Check if any challenges are now satisfied
    services.evaluate_challenges_for_user(instance.student)


# ── Assignment submitted ───────────────────────────────────────────

@receiver(post_save, sender=Submission)
def on_submission_save(sender, instance: Submission, created, **kwargs):
    """Award XP when a student submits an assignment for the first time."""
    if not created:
        return  # ignore re-submissions (update_fields saves)
    if not instance.student.is_student:
        return

    services.award_xp(
        user=instance.student,
        amount=services.XP_ASSIGNMENT_SUBMIT,
        reason='assignment_submit',
        description=f'Submitted: {instance.assignment.title}',
    )

    services.record_task_completion(instance.student)
    services.evaluate_challenges_for_user(instance.student)


# ── Grade recorded ────────────────────────────────────────────────

@receiver(post_save, sender=Grade)
def on_grade_save(sender, instance: Grade, created, **kwargs):
    """Award bonus XP for high grades."""
    if not created:
        return
    student = instance.submission.student
    if not student.is_student:
        return

    pct = instance.percentage
    if pct >= 90:
        bonus = services.XP_GRADE_HIGH
        label = 'A-grade bonus'
    elif pct >= 70:
        bonus = services.XP_GRADE_MID
        label = 'Good-grade bonus'
    else:
        return  # No bonus for grades below 70%

    services.award_xp(
        user=student,
        amount=bonus,
        reason='grade_bonus',
        description=f'{label} on {instance.submission.assignment.title} ({pct}%)',
    )

    services.check_and_award_badges(student)


# ── Challenge completed ────────────────────────────────────────────

@receiver(post_save, sender=ChallengeCompletion)
def on_challenge_completion_save(sender, instance: ChallengeCompletion, created, **kwargs):
    """
    Badge milestone checks after completing a challenge.
    (XP & freeze are awarded inside services._complete_challenge before this runs.)
    """
    if created:
        services.check_and_award_badges(instance.user)
