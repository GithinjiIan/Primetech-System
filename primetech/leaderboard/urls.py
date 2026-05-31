"""URL configuration for the leaderboard app."""

from django.urls import path
from . import views

app_name = 'leaderboard'

urlpatterns = [
    # Global leaderboard  (?period=all_time|monthly|weekly)
    path('', views.leaderboard_view, name='leaderboard'),

    # Public student gamification profile
    path('profile/<int:user_id>/', views.public_profile_view, name='public_profile'),

    # Daily challenges (student view)
    path('challenges/', views.challenge_list_view, name='challenges'),

    # Staff: create instructor challenge
    path('challenges/create/', views.staff_create_challenge_view, name='create_challenge'),

    # AJAX activity heartbeat
    path('ping/', views.ping_activity_view, name='ping_activity'),
]
