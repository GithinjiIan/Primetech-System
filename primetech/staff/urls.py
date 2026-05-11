from django.urls import path
from . import views

app_name = 'staff'

urlpatterns = [
    path('course_allocation/', views.course_allocation, name='course_allocation'),
    path('class_sessions/', views.class_sessions, name='sessions'),
    path('students_rollcall/', views.students_rollcall, name='students_rollcall'),
    path('student_submissions/', views.student_submissions, name='submissions'),
    path('courses_setup/', views.courses_setup, name='courses_setup'),
    path('staff_dashboard/', views.staff_dashboard, name='dashboard'),
    
    
]
