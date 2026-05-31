"""
Views for the leaderboard app.
"""

import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import student_required
from .models import (
    GamificationProfile,
    DailyChallenge,
    ChallengeCompletion,
    UserBadge,
    ActivitySession,
    XPTransaction,
)
from . import services
from .forms import DailyChallengeForm

User = get_user_model()
logger = logging.getLogger(__name__)


# ── Decorator for staff-only pages ────────────────────────────────
def staff_required(view_func):
    from django.contrib.auth.decorators import user_passes_test
    return user_passes_test(
        lambda u: u.is_authenticated and u.role in ('staff', 'superadmin'),
        login_url='accounts:login',
    )(view_func)


# ─────────────────────────────────────────────────────────────────
# Global Leaderboard
# ─────────────────────────────────────────────────────────────────

@login_required
def leaderboard_view(request):
    """
    Global leaderboard ranked by XP.
    Supports ?period=all_time|monthly|weekly query param.
    Always shows the current user's rank even if outside top 10.
    """
    period = request.GET.get('period', 'all_time')
    if period not in ('all_time', 'monthly', 'weekly'):
        period = 'all_time'

    board = services.get_leaderboard(period, limit=50)

    # Annotate rank
    for idx, profile in enumerate(board, start=1):
        profile.rank = idx

    # Current user's position
    user_rank    = None
    user_profile = None
    if request.user.is_student:
        user_rank    = services.get_user_rank(request.user, period)
        user_profile = services.get_or_create_profile(request.user)

    # Top 3 for podium
    top3 = board[:3]

    return render(request, 'leaderboard/leaderboard.html', {
        'board':        board,
        'top3':         top3,
        'period':       period,
        'user_rank':    user_rank,
        'user_profile': user_profile,
    })


# ─────────────────────────────────────────────────────────────────
# Public Student Profile
# ─────────────────────────────────────────────────────────────────

@login_required
def public_profile_view(request, user_id):
    """Public gamification profile visible to all authenticated users."""
    profile_user = get_object_or_404(User, pk=user_id, role='student', is_active=True)
    profile      = services.get_or_create_profile(profile_user)
    badges       = UserBadge.objects.filter(user=profile_user).select_related('badge').order_by('-awarded_at')
    recent_xp    = XPTransaction.objects.filter(user=profile_user).order_by('-created_at')[:10]
    user_rank    = services.get_user_rank(profile_user, 'all_time')

    from courses.models import MaterialProgress
    completed_materials = (
        MaterialProgress.objects
        .filter(student=profile_user, completed=True)
        .select_related('material', 'material__course')
        .order_by('-completed_at')[:15]
    )

    return render(request, 'leaderboard/public_profile.html', {
        'profile_user':        profile_user,
        'profile':             profile,
        'badges':              badges,
        'recent_xp':           recent_xp,
        'user_rank':           user_rank,
        'completed_materials': completed_materials,
    })


# ─────────────────────────────────────────────────────────────────
# Daily Challenges
# ─────────────────────────────────────────────────────────────────

@student_required
def challenge_list_view(request):
    """Show today's challenges and the student's completion status."""
    today      = timezone.localdate()
    challenges = DailyChallenge.objects.filter(date=today).order_by('is_auto_generated', 'title')

    done_ids = set(
        ChallengeCompletion.objects
        .filter(user=request.user, challenge__date=today)
        .values_list('challenge_id', flat=True)
    )

    # Attach progress percentage to each challenge
    profile = services.get_or_create_profile(request.user)
    for ch in challenges:
        ch.is_done = ch.pk in done_ids
        ch.progress_pct = _challenge_progress_pct(ch, request.user, profile)

    return render(request, 'leaderboard/challenges.html', {
        'challenges': challenges,
        'today':      today,
        'profile':    profile,
    })


def _challenge_progress_pct(ch: DailyChallenge, user, profile) -> int:
    """Return 0–100 progress % for a challenge (for UI progress rings)."""
    today = timezone.localdate()
    if ch.target_count <= 0:
        return 0

    if ch.challenge_type == 'complete_materials':
        from courses.models import MaterialProgress
        done = MaterialProgress.objects.filter(
            student=user, completed=True, completed_at__date=today
        ).count()
        return min(100, int(done / ch.target_count * 100))
    if ch.challenge_type == 'submit_assignments':
        from courses.models import Submission
        done = Submission.objects.filter(student=user, submitted_at__date=today).count()
        return min(100, int(done / ch.target_count * 100))
    if ch.challenge_type == 'active_minutes':
        from .models import ActivitySession
        from django.db.models import Sum
        total_sec = ActivitySession.objects.filter(
            user=user, session_date=today
        ).aggregate(t=Sum('duration_seconds'))['t'] or 0
        minutes = total_sec // 60
        return min(100, int(minutes / ch.target_count * 100))
    if ch.challenge_type == 'earn_xp':
        from django.db.models import Sum
        today_xp = XPTransaction.objects.filter(
            user=user, created_at__date=today, xp_amount__gt=0
        ).aggregate(t=Sum('xp_amount'))['t'] or 0
        return min(100, int(today_xp / ch.target_count * 100))
    return 0


# ─────────────────────────────────────────────────────────────────
# Staff: Create Challenge
# ─────────────────────────────────────────────────────────────────

@staff_required
def staff_create_challenge_view(request):
    """Staff form to create an instructor-defined challenge."""
    if request.method == 'POST':
        form = DailyChallengeForm(request.POST)
        if form.is_valid():
            challenge = form.save(commit=False)
            challenge.is_auto_generated = False
            challenge.created_by        = request.user
            challenge.save()
            messages.success(request, f'Challenge "{challenge.title}" created for {challenge.date}!')
            return redirect('leaderboard:challenges')
    else:
        form = DailyChallengeForm()

    return render(request, 'leaderboard/create_challenge.html', {'form': form})


# ─────────────────────────────────────────────────────────────────
# AJAX: Activity heartbeat ping
# ─────────────────────────────────────────────────────────────────

@require_POST
@login_required
def ping_activity_view(request):
    """
    AJAX endpoint called every 5 minutes by the frontend JS.
    Updates (or creates) an ActivitySession for today.
    """
    if not request.user.is_student:
        return JsonResponse({'status': 'ignored'})

    today   = timezone.localdate()
    session = ActivitySession.objects.filter(
        user=request.user, session_date=today
    ).order_by('-started_at').first()

    if session is None:
        session = ActivitySession.objects.create(user=request.user, session_date=today)
    else:
        session.ping()

    # After updating time, check if streak is now satisfied
    services.record_task_completion(request.user)

    return JsonResponse({
        'status':          'ok',
        'duration_minutes': session.duration_minutes,
    })
