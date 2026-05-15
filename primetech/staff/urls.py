from django.urls import path
from . import views

app_name = 'staff'

urlpatterns = [
    path('dashboard/', views.staff_dashboard, name='dashboard'),
    path('course_allocation/', views.course_allocation, name='course_allocation'),
    path('students_rollcall/', views.students_rollcall, name='students_rollcall'),
    path('courses_setup/', views.courses_setup, name='courses_setup'),
    path('class_sessions/', views.class_sessions, name='sessions'),
    path('assignments/', views.manage_assignments, name='assignments'),
    path('submissions/', views.student_submissions, name='submissions'),
    path('submissions/<int:submission_id>/grade/', views.grade_submission, name='grade_submission'),
    path('notifications/send/', views.send_notification, name='send_notification'),
]
