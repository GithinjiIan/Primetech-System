from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('partnership/', views.partnership, name='partnership'),
    path('courses/', views.courses, name='courses'),
    path('courses/<int:course_id>/apply/', views.apply_for_course, name='apply_for_course'),
    path('newsletter-signup/', views.newsletter_signup, name='newsletter_signup'),
]