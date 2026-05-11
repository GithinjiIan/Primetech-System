from django.shortcuts import render
from website.models import Course, Enrollment
from accounts.decorators import staff_required
from notifications.models import Notification

# Create your views here.

@staff_required
def course_allocation(request):
    allocated_courses = Course.objects.filter(assigned_instructor=request.user)
    return render(request, 'staff/course_allocation.html', {'allocated_courses': allocated_courses})


@staff_required
def courses_setup(request):
    allocated_courses = Course.objects.filter(assigned_instructor=request.user)
    return render(request, 'staff/courses_setup.html', {'allocated_courses': allocated_courses})

@staff_required
def students_rollcall(request):
    # Fetch courses assigned to this instructor and their students
    allocated_courses = Course.objects.filter(assigned_instructor=request.user).prefetch_related('enrollments__student')
    
    # Process data for template (if needed, or use related names in template)
    for course in allocated_courses:
        course.enrolled_students = course.enrollments.all()
        
    return render(request, 'staff/students_rollcall.html', {'allocated_courses': allocated_courses})


@staff_required
def student_submissions(request):
    # For now, we can pass dummy submissions or fetch real ones if models exist
    # submissions = Submission.objects.filter(course__assigned_instructor=request.user)
    return render(request, 'staff/submissions.html', {'submissions': []})

@staff_required
def class_sessions(request):
    allocated_courses = Course.objects.filter(assigned_instructor=request.user)
    return render(request, 'staff/sessions_schedule.html', {'allocated_courses': allocated_courses})

@staff_required
def staff_dashboard(request):
    """Staff/instructor dashboard: shows assigned courses and students."""
    courses = Course.objects.filter(
        assigned_instructor=request.user, is_active=True
    )
    enrollments = Enrollment.objects.filter(
        course__assigned_instructor=request.user
    ).select_related('student', 'course')

    notifications = Notification.objects.filter(
        recipient=request.user
    ).order_by('-created_at')[:10]

    return render(request, 'staff/dashboard.html', {
        'courses': courses,
        'enrollments': enrollments,
        'notifications': notifications,
    })