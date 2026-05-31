"""Forms for the leaderboard / gamification app."""

from django import forms
from .models import DailyChallenge


class DailyChallengeForm(forms.ModelForm):
    class Meta:
        model  = DailyChallenge
        fields = [
            'date', 'title', 'description',
            'challenge_type', 'target_count',
            'xp_reward', 'reward_type', 'badge_reward',
        ]
        widgets = {
            'date':           forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'title':          forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Complete 3 modules today'}),
            'description':    forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'challenge_type': forms.Select(attrs={'class': 'form-select'}),
            'target_count':   forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'xp_reward':      forms.NumberInput(attrs={'class': 'form-control', 'min': 10}),
            'reward_type':    forms.Select(attrs={'class': 'form-select'}),
            'badge_reward':   forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'target_count': 'Target Count (N)',
            'xp_reward':    'XP Reward',
            'reward_type':  'Reward Type',
            'badge_reward': 'Badge Reward (optional)',
        }
