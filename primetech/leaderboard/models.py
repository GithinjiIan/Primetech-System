"""
Gamification & Social Engagement models for PrimeTech LMS.

Provides:
  - GamificationProfile  : XP, streaks, freeze counts per student
  - Badge / UserBadge    : achievement badges
  - DailyChallenge       : auto-generated + instructor challenges
  - ChallengeCompletion  : per-user challenge tracking
  - ActivitySession      : 30-minute interaction tracking
  - XPTransaction        : audit log of every XP grant
"""

from django.db import models
from django.conf import settings
from django.core.validators import RegexValidator
from django.utils import timezone


# ── XP Constants ──────────────────────────────────────────────────
XP_MATERIAL_COMPLETE   = 20
XP_ASSIGNMENT_SUBMIT   = 30
XP_GRADE_HIGH          = 50   # ≥ 90 %
XP_GRADE_MID           = 20   # 70–89 %
XP_CHALLENGE_COMPLETE  = 100
XP_BADGE_EARNED        = 10

STREAK_MIN_TASKS         = 2   # tasks required in a day
STREAK_MIN_MINUTES       = 30  # minimum active minutes in a day


# ── Gamification Profile ──────────────────────────────────────────
class GamificationProfile(models.Model):
    """One-to-one gamification state for every student."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='gamification_profile',
    )

    total_xp          = models.PositiveIntegerField(default=0)
    current_streak    = models.PositiveIntegerField(default=0)
    longest_streak    = models.PositiveIntegerField(default=0)
    freeze_count      = models.PositiveSmallIntegerField(default=0)

    # Date of last qualifying activity (used for streak calculation)
    last_activity_date = models.DateField(null=True, blank=True)

    # Daily task counter — reset each day by the midnight Celery task
    tasks_today       = models.PositiveSmallIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Gamification Profile'
        verbose_name_plural = 'Gamification Profiles'

    def __str__(self):
        return f"{self.user.get_full_name()} — {self.total_xp} XP | 🔥{self.current_streak}"

    @property
    def rank_display(self):
        """Human-friendly XP rank title."""
        if self.total_xp < 200:    return 'Beginner'
        if self.total_xp < 500:    return 'Explorer'
        if self.total_xp < 1000:   return 'Achiever'
        if self.total_xp < 2500:   return 'Expert'
        if self.total_xp < 5000:   return 'Master'
        return 'Legend'

    @property
    def rank_color(self):
        mapping = {
            'Beginner': '#6c757d',
            'Explorer': '#0d6efd',
            'Achiever': '#198754',
            'Expert':   '#fd7e14',
            'Master':   '#dc3545',
            'Legend':   '#6f42c1',
        }
        return mapping.get(self.rank_display, '#6c757d')


# ── Badge ──────────────────────────────────────────────────────────
class Badge(models.Model):
    """A badge that can be earned by students for specific achievements."""

    CRITERIA_CHOICES = [
        ('streak_7',       '7-Day Streak'),
        ('streak_30',      '30-Day Streak'),
        ('streak_100',     '100-Day Streak'),
        ('course_complete','Course Completed'),
        ('top3_leaderboard','Top 3 on Leaderboard'),
        ('module_master',  'Module Master (10 materials)'),
        ('first_submit',   'First Assignment Submitted'),
        ('xp_500',         '500 XP Milestone'),
        ('xp_1000',        '1 000 XP Milestone'),
        ('xp_5000',        '5 000 XP Milestone'),
        ('challenge_10',   '10 Challenges Completed'),
        ('custom',         'Custom / Manual'),
    ]

    name          = models.CharField(max_length=100, unique=True)
    slug          = models.SlugField(max_length=100, unique=True)
    description   = models.TextField()
    icon          = models.CharField(
        max_length=50,
        default='fas fa-award',
        validators=[
            RegexValidator(
                regex=r'^fa[srb]? fa-[a-z0-9\-]+$',
                message='Icon must be a valid Font Awesome class like "fas fa-award".',
            )
        ],
        help_text='Font Awesome class, e.g. "fas fa-fire"',
    )
    icon_color    = models.CharField(
        max_length=20,
        default='#fd7e14',
        validators=[
            RegexValidator(
                regex=r'^#[0-9A-Fa-f]{6}$',
                message='Icon color must be a 6-digit hex code, e.g. #fd7e14.',
            )
        ],
    )
    criteria_type = models.CharField(max_length=30, choices=CRITERIA_CHOICES, default='custom')
    xp_reward     = models.PositiveSmallIntegerField(default=10)
    is_active     = models.BooleanField(default=True)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Badge'
        verbose_name_plural = 'Badges'
        ordering            = ['name']

    def __str__(self):
        return self.name


class UserBadge(models.Model):
    """Records which badges a user has earned and when."""

    user   = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='user_badges',
    )
    badge      = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name='user_badges')
    awarded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together     = ['user', 'badge']
        verbose_name        = 'User Badge'
        verbose_name_plural = 'User Badges'
        ordering            = ['-awarded_at']

    def __str__(self):
        return f"{self.user.get_full_name()} — {self.badge.name}"


# ── Daily Challenge ───────────────────────────────────────────────
class DailyChallenge(models.Model):
    """A challenge (auto-generated or instructor-created) for a specific day."""

    CHALLENGE_TYPE_CHOICES = [
        ('complete_materials', 'Complete N Materials'),
        ('submit_assignments', 'Submit N Assignments'),
        ('active_minutes',     'Be Active for N Minutes'),
        ('earn_xp',            'Earn N XP Today'),
        ('custom',             'Custom Task'),
    ]

    REWARD_TYPE_CHOICES = [
        ('xp',    'XP Only'),
        ('freeze', 'Streak Freeze'),
        ('badge',  'Badge'),
        ('xp_freeze', 'XP + Streak Freeze'),
    ]

    date            = models.DateField(default=timezone.localdate)
    title           = models.CharField(max_length=200)
    description     = models.TextField()
    challenge_type  = models.CharField(max_length=30, choices=CHALLENGE_TYPE_CHOICES, default='complete_materials')
    target_count    = models.PositiveSmallIntegerField(default=3)
    xp_reward       = models.PositiveSmallIntegerField(default=100)
    reward_type     = models.CharField(max_length=20, choices=REWARD_TYPE_CHOICES, default='xp')
    badge_reward    = models.ForeignKey(
        Badge, on_delete=models.SET_NULL, null=True, blank=True, related_name='challenge_rewards'
    )
    is_auto_generated = models.BooleanField(default=True)
    created_by      = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_challenges',
    )
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Daily Challenge'
        verbose_name_plural = 'Daily Challenges'
        ordering            = ['-date', 'title']

    def __str__(self):
        return f"[{self.date}] {self.title}"

    @property
    def is_today(self):
        return self.date == timezone.localdate()


class ChallengeCompletion(models.Model):
    """Records that a user completed a daily challenge."""

    user        = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='challenge_completions',
    )
    challenge   = models.ForeignKey(DailyChallenge, on_delete=models.CASCADE, related_name='completions')
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together     = ['user', 'challenge']
        verbose_name        = 'Challenge Completion'
        verbose_name_plural = 'Challenge Completions'

    def __str__(self):
        return f"{self.user.get_full_name()} ✓ {self.challenge.title}"


# ── Activity Session ───────────────────────────────────────────────
class ActivitySession(models.Model):
    """
    Tracks a student's active session for the 30-minute streak requirement.
    Updated by an AJAX heartbeat ping every 5 minutes.
    """

    user          = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='activity_sessions',
    )
    started_at    = models.DateTimeField(default=timezone.now)
    last_ping     = models.DateTimeField(default=timezone.now)
    # Total seconds of activity (accumulated across pings)
    duration_seconds = models.PositiveIntegerField(default=0)
    session_date  = models.DateField(default=timezone.localdate)

    class Meta:
        verbose_name        = 'Activity Session'
        verbose_name_plural = 'Activity Sessions'
        ordering            = ['-started_at']
        # One open session per user per day is the norm; duplicates may exist for edge cases
        indexes             = [models.Index(fields=['user', 'session_date'])]

    def __str__(self):
        return f"{self.user.get_full_name()} — {self.session_date} ({self.duration_seconds // 60} min)"

    @property
    def duration_minutes(self):
        return self.duration_seconds // 60

    def ping(self):
        """Call on each heartbeat to accumulate duration."""
        now = timezone.now()
        gap = (now - self.last_ping).total_seconds()
        # Count gap only if the student was actually active (≤ 10 min gap = still active)
        if gap <= 600:
            self.duration_seconds += int(gap)
        self.last_ping = now
        self.save(update_fields=['last_ping', 'duration_seconds'])


# ── XP Transaction Log ─────────────────────────────────────────────
class XPTransaction(models.Model):
    """Audit trail for every XP grant."""

    REASON_CHOICES = [
        ('material_complete',  'Material Completed'),
        ('assignment_submit',  'Assignment Submitted'),
        ('grade_bonus',        'High-Grade Bonus'),
        ('challenge_complete', 'Challenge Completed'),
        ('badge_earned',       'Badge Earned'),
        ('admin_grant',        'Admin Manual Grant'),
    ]

    user       = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='xp_transactions',
    )
    xp_amount  = models.SmallIntegerField()          # Can be negative for admin adjustments
    reason     = models.CharField(max_length=30, choices=REASON_CHOICES)
    material_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'XP Transaction'
        verbose_name_plural = 'XP Transactions'
        ordering            = ['-created_at']
        unique_together     = ['user', 'reason', 'material_id']

    def __str__(self):
        sign = '+' if self.xp_amount >= 0 else ''
        return f"{self.user.get_full_name()} {sign}{self.xp_amount} XP — {self.get_reason_display()}"
