from django.urls import path
from .import views

#-------- Students urls-------------
app_name = 'students'

urlpatterns = [
    path('student_sessions/', views.student_sessions, name='sessions'),
    path('course_enroll/', views.course_enroll, name='enroll' ),
    path('my_courses/', views.my_courses, name='my_courses'),
    path('student_profile/', views.student_profile, name='student_profile'),
    path('student_submissions/', views.student_submissions, name='submissions'),
    path('dashboard/', views.student_dashboard, name='dashboard'),
]