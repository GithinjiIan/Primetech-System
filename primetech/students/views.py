from django.shortcuts import render
from website.models import Enrollment
from accounts.decorators import student_required
from notifications.models import Notification

# Create your views here.
@student_required
def student_sessions(request):
    return render(request, 'students/class_sessions.html')

@student_required
def course_enroll(request):
    return render(request, 'students/course_enroll.html')

@student_required
def my_courses(request):
    from website.models import Course
    courses = Course.objects.filter(is_active=True)
    return render(request, 'students/my_courses.html', {'courses': courses})

@student_required
def student_profile(request):
    return render(request, 'students/student_profile.html')

@student_required
def student_submissions(request):
    return render(request, 'students/student_submissions.html')

@student_required
def student_dashboard(request):
    """Student dashboard: shows enrolled courses and notifications."""
    enrollments = Enrollment.objects.filter(
        student=request.user
    ).select_related('course', 'course__category')

    notifications = Notification.objects.filter(
        recipient=request.user
    ).order_by('-created_at')[:10]

    return render(request, 'students/dashboard.html', {
        'enrollments': enrollments,
        'notifications': notifications,
    })