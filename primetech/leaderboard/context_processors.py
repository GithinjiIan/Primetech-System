"""
Context processors for the leaderboard / gamification app.
Makes the current user's GamificationProfile available in templates.
"""

def gamification_context(request):
    """
    Adds 'gamification_profile' to the context for authenticated students.
    """
    if request.user.is_authenticated and request.user.is_student:
        if hasattr(request, '_cached_gamification_profile'):
            return {'gamification_profile': request._cached_gamification_profile}

        from leaderboard.services import get_or_create_profile
        try:
            profile = get_or_create_profile(request.user)
            request._cached_gamification_profile = profile
            return {
                'gamification_profile': profile
            }
        except Exception:
            pass
    return {}
