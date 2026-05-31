"""
Django Admin configuration for the leaderboard / gamification app.
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import (
    GamificationProfile,
    Badge,
    UserBadge,
    DailyChallenge,
    ChallengeCompletion,
    ActivitySession,
    XPTransaction,
)


# ── Gamification Profile ──────────────────────────────────────────
@admin.register(GamificationProfile)
class GamificationProfileAdmin(admin.ModelAdmin):
    list_display  = ('user', 'total_xp', 'rank_display', 'current_streak', 'longest_streak', 'freeze_count', 'last_activity_date')
    list_filter   = ('last_activity_date',)
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('created_at', 'updated_at', 'rank_display', 'rank_color')
    ordering      = ('-total_xp',)

    def rank_display(self, obj):
        color = obj.rank_color
        return format_html(
            '<span style="color:{}; font-weight:bold;">{}</span>',
            color, obj.rank_display,
        )
    rank_display.short_description = 'Rank'


# ── Badge ─────────────────────────────────────────────────────────
@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display  = ('icon_preview', 'name', 'criteria_type', 'xp_reward', 'is_active')
    list_filter   = ('criteria_type', 'is_active')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ('xp_reward', 'is_active')

    def icon_preview(self, obj):
        return format_html(
            '<i class="{}" style="color:{}; font-size:1.4rem;"></i>',
            obj.icon, obj.icon_color,
        )
    icon_preview.short_description = 'Icon'


# ── User Badge ────────────────────────────────────────────────────
@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    list_display  = ('user', 'badge', 'awarded_at')
    list_filter   = ('badge', 'awarded_at')
    search_fields = ('user__email', 'user__first_name', 'badge__name')
    date_hierarchy = 'awarded_at'


# ── Daily Challenge ───────────────────────────────────────────────
@admin.register(DailyChallenge)
class DailyChallengeAdmin(admin.ModelAdmin):
    list_display  = ('title', 'date', 'challenge_type', 'target_count', 'xp_reward', 'reward_type', 'is_auto_generated', 'completions_count')
    list_filter   = ('date', 'challenge_type', 'reward_type', 'is_auto_generated')
    search_fields = ('title', 'description')
    date_hierarchy = 'date'

    def completions_count(self, obj):
        return obj.completions.count()
    completions_count.short_description = 'Completions'


# ── Challenge Completion ──────────────────────────────────────────
@admin.register(ChallengeCompletion)
class ChallengeCompletionAdmin(admin.ModelAdmin):
    list_display  = ('user', 'challenge', 'completed_at')
    list_filter   = ('challenge__date',)
    search_fields = ('user__email', 'challenge__title')
    date_hierarchy = 'completed_at'


# ── Activity Session ──────────────────────────────────────────────
@admin.register(ActivitySession)
class ActivitySessionAdmin(admin.ModelAdmin):
    list_display  = ('user', 'session_date', 'duration_minutes_display', 'started_at', 'last_ping')
    list_filter   = ('session_date',)
    search_fields = ('user__email', 'user__first_name')
    date_hierarchy = 'session_date'

    def duration_minutes_display(self, obj):
        return f"{obj.duration_minutes} min"
    duration_minutes_display.short_description = 'Duration'


# ── XP Transaction ────────────────────────────────────────────────
@admin.register(XPTransaction)
class XPTransactionAdmin(admin.ModelAdmin):
    list_display  = ('user', 'xp_amount_display', 'reason', 'description', 'created_at')
    list_filter   = ('reason', 'created_at')
    search_fields = ('user__email', 'user__first_name', 'description')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)

    def xp_amount_display(self, obj):
        color = '#198754' if obj.xp_amount >= 0 else '#dc3545'
        sign  = '+' if obj.xp_amount >= 0 else ''
        return format_html(
            '<strong style="color:{};">{}{} XP</strong>',
            color, sign, obj.xp_amount,
        )
    xp_amount_display.short_description = 'XP'
