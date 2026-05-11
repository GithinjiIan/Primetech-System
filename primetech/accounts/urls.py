"""
URL configuration for the accounts app.
"""
from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # Authentication
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Password management
    path('password/change/', views.force_password_change, name='force_password_change'),
    path('password/forgot/', views.forgot_password_view, name='forgot_password'),
    path('password/reset/<uidb64>/<token>/',
         views.password_reset_confirm_view, name='password_reset_confirm'),

    # Email verification
    path('verify-email/<uidb64>/<token>/', views.verify_email, name='verify_email'),

    # Dashboards are now handled in their respective apps
]
