from django.urls import path
from . import views

app_name = 'students'

urlpatterns = [
    path('dashboard/', views.student_dashboard, name='dashboard'),
    path('my_courses/', views.my_courses, name='my_courses'),
    path('course/<int:course_id>/materials/', views.course_materials, name='course_materials'),
    path('course/<int:course_id>/material/<int:material_id>/', views.material_detail, name='material_detail'),
    path('sessions/', views.student_sessions, name='sessions'),
    path('submissions/', views.student_submissions, name='submissions'),
    path('submissions/<int:assignment_id>/submit/', views.submit_assignment, name='submit_assignment'),
    path('profile/', views.student_profile, name='student_profile'),
    path('enroll/', views.course_enroll, name='enroll'),
]