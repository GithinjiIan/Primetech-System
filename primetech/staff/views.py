"""
Staff views: course content management, sessions, assignments, grading, notifications.
"""
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Count, Q

from website.models import Course, Enrollment
from accounts.decorators import staff_required
from notifications.models import Notification
from courses.models import CourseMaterial, ClassSession, Assignment, Submission, Grade
from courses.forms import (
    CourseMaterialForm, ClassSessionForm, AssignmentForm,
    GradeForm, StaffNotificationForm
)

logger = logging.getLogger(__name__)


# ── Dashboard ────────────────────────────────────────────────────
@staff_required
def staff_dashboard(request):
    """Staff/instructor dashboard: assigned courses, students, recent submissions."""
    courses = Course.objects.filter(assigned_instructor=request.user, is_active=True)
    enrollments = Enrollment.objects.filter(
        course__assigned_instructor=request.user
    ).select_related('student', 'course')
    notifications = Notification.objects.filter(
        recipient=request.user
    ).order_by('-created_at')[:10]

    # Pending submissions count
    pending_submissions = Submission.objects.filter(
        assignment__course__assigned_instructor=request.user,
        grade__isnull=True,
    )
    recent_submissions = Submission.objects.filter(
        assignment__course__assigned_instructor=request.user
    ).select_related('student', 'assignment', 'assignment__course').order_by('-submitted_at')[:5]

    return render(request, 'staff/dashboard.html', {
        'courses': courses,
        'allocated_courses': courses,
        'enrollments': enrollments,
        'notifications': notifications,
        'total_students': enrollments.values('student').distinct().count(),
        'pending_submissions_count': pending_submissions.count(),
        'recent_submissions': recent_submissions,
    })


# ── Course Allocation ─────────────────────────────────────────────
@staff_required
def course_allocation(request):
    allocated_courses = Course.objects.filter(
        assigned_instructor=request.user
    ).annotate(students_count=Count('enrollments'))
    return render(request, 'staff/course_allocation.html', {'allocated_courses': allocated_courses})


# ── Students Roll Call ────────────────────────────────────────────
@staff_required
def students_rollcall(request):
    allocated_courses = Course.objects.filter(
        assigned_instructor=request.user
    ).prefetch_related('enrollments__student')
    for course in allocated_courses:
        course.enrolled_students = course.enrollments.filter(status='active').select_related('student')
    return render(request, 'staff/students_rollcall.html', {'allocated_courses': allocated_courses})


# ── Course Content (Materials) ────────────────────────────────────
@staff_required
def courses_setup(request):
    """List and manage materials for a selected course."""
    allocated_courses = Course.objects.filter(assigned_instructor=request.user, is_active=True)
    selected_course = None
    materials = []
    form = None

    course_id = request.GET.get('course_id') or request.POST.get('course_id')
    if course_id:
        selected_course = get_object_or_404(Course, pk=course_id, assigned_instructor=request.user)
        materials = CourseMaterial.objects.filter(course=selected_course).order_by('order')

        if request.method == 'POST':
            action = request.POST.get('action')

            if action == 'add_material':
                form = CourseMaterialForm(request.POST, request.FILES)
                if form.is_valid():
                    material = form.save(commit=False)
                    material.course = selected_course
                    material.created_by = request.user
                    material.save()
                    messages.success(request, f'Material "{material.title}" added successfully.')
                    return redirect(f'{request.path}?course_id={selected_course.pk}')

            elif action == 'delete_material':
                mat_id = request.POST.get('material_id')
                mat = get_object_or_404(CourseMaterial, pk=mat_id, course=selected_course)
                mat.delete()
                messages.success(request, 'Material deleted.')
                return redirect(f'{request.path}?course_id={selected_course.pk}')

    if form is None:
        form = CourseMaterialForm()

    return render(request, 'staff/courses_setup.html', {
        'allocated_courses': allocated_courses,
        'selected_course': selected_course,
        'materials': materials,
        'form': form,
    })


# ── Class Sessions ────────────────────────────────────────────────
@staff_required
def class_sessions(request):
    """Manage class sessions for assigned courses."""
    allocated_courses = Course.objects.filter(assigned_instructor=request.user)
    selected_course = None
    sessions = []
    form = ClassSessionForm()

    course_id = request.GET.get('course_id') or request.POST.get('course_id')
    if course_id:
        selected_course = get_object_or_404(Course, pk=course_id, assigned_instructor=request.user)
        sessions = ClassSession.objects.filter(course=selected_course).order_by('session_date', 'start_time')

        if request.method == 'POST':
            action = request.POST.get('action')

            if action == 'add_session':
                form = ClassSessionForm(request.POST)
                if form.is_valid():
                    session = form.save(commit=False)
                    session.course = selected_course
                    session.created_by = request.user
                    session.save()
                    # Notify all enrolled students
                    _notify_course_students(
                        course=selected_course,
                        title=f'New Session: {session.title}',
                        message=f'A new class session "{session.title}" has been scheduled for '
                                f'{session.session_date.strftime("%b %d, %Y")} at '
                                f'{session.start_time.strftime("%I:%M %p")}.',
                    )
                    messages.success(request, f'Session "{session.title}" created.')
                    return redirect(f'{request.path}?course_id={selected_course.pk}')

            elif action == 'delete_session':
                sess_id = request.POST.get('session_id')
                sess = get_object_or_404(ClassSession, pk=sess_id, course=selected_course)
                sess.delete()
                messages.success(request, 'Session deleted.')
                return redirect(f'{request.path}?course_id={selected_course.pk}')

    return render(request, 'staff/sessions_schedule.html', {
        'allocated_courses': allocated_courses,
        'selected_course': selected_course,
        'sessions': sessions,
        'form': form,
    })


# ── Assignments ───────────────────────────────────────────────────
@staff_required
def manage_assignments(request):
    """Create and list assignments for assigned courses."""
    allocated_courses = Course.objects.filter(assigned_instructor=request.user)
    selected_course = None
    assignments = []
    form = AssignmentForm()

    course_id = request.GET.get('course_id') or request.POST.get('course_id')
    if course_id:
        selected_course = get_object_or_404(Course, pk=course_id, assigned_instructor=request.user)
        assignments = Assignment.objects.filter(course=selected_course).annotate(
            sub_count=Count('submissions'),
            pending_count=Count('submissions', filter=Q(submissions__grade__isnull=True))
        )

        if request.method == 'POST':
            action = request.POST.get('action')

            if action == 'add_assignment':
                form = AssignmentForm(request.POST, request.FILES)
                if form.is_valid():
                    assignment = form.save(commit=False)
                    assignment.course = selected_course
                    assignment.created_by = request.user
                    assignment.save()
                    _notify_course_students(
                        course=selected_course,
                        title=f'New Assignment: {assignment.title}',
                        message=f'A new assignment "{assignment.title}" has been posted in '
                                f'"{selected_course.title}". Due: {assignment.due_date.strftime("%b %d, %Y %I:%M %p")}.',
                    )
                    messages.success(request, f'Assignment "{assignment.title}" created.')
                    return redirect(f'{request.path}?course_id={selected_course.pk}')

            elif action == 'delete_assignment':
                asgn_id = request.POST.get('assignment_id')
                asgn = get_object_or_404(Assignment, pk=asgn_id, course=selected_course)
                asgn.delete()
                messages.success(request, 'Assignment deleted.')
                return redirect(f'{request.path}?course_id={selected_course.pk}')

    return render(request, 'staff/assignments.html', {
        'allocated_courses': allocated_courses,
        'selected_course': selected_course,
        'assignments': assignments,
        'form': form,
    })


# ── Student Submissions (grading) ─────────────────────────────────
@staff_required
def student_submissions(request):
    """View and grade student submissions for instructor's courses."""
    course_filter = request.GET.get('course_id')
    status_filter = request.GET.get('status', '')

    submissions_qs = Submission.objects.filter(
        assignment__course__assigned_instructor=request.user
    ).select_related('student', 'assignment', 'assignment__course').order_by('-submitted_at')

    if course_filter:
        submissions_qs = submissions_qs.filter(assignment__course_id=course_filter)
    if status_filter:
        submissions_qs = submissions_qs.filter(status=status_filter)

    allocated_courses = Course.objects.filter(assigned_instructor=request.user)

    return render(request, 'staff/submissions.html', {
        'submissions': submissions_qs,
        'allocated_courses': allocated_courses,
        'course_filter': course_filter,
        'status_filter': status_filter,
    })


@staff_required
def grade_submission(request, submission_id):
    """Grade a specific student submission."""
    submission = get_object_or_404(
        Submission,
        pk=submission_id,
        assignment__course__assigned_instructor=request.user
    )
    grade_instance = getattr(submission, 'grade', None)

    if request.method == 'POST':
        form = GradeForm(request.POST, instance=grade_instance)
        if form.is_valid():
            grade = form.save(commit=False)
            grade.submission = submission
            grade.graded_by = request.user
            grade.save()
            submission.status = 'graded'
            submission.save(update_fields=['status'])

            # Notify student
            from notifications.utils import create_notification
            create_notification(
                recipient=submission.student,
                notification_type='course',
                title=f'Assignment Graded: {submission.assignment.title}',
                message=f'Your submission for "{submission.assignment.title}" in '
                        f'"{submission.assignment.course.title}" has been graded. '
                        f'Score: {grade.score}/{submission.assignment.max_score}.',
            )
            messages.success(request, f'Grade saved for {submission.student.get_full_name()}.')
            return redirect('staff:submissions')
    else:
        form = GradeForm(instance=grade_instance)

    return render(request, 'staff/grade_submission.html', {
        'submission': submission,
        'form': form,
        'grade': grade_instance,
    })


# ── Staff Notifications ───────────────────────────────────────────
@staff_required
def send_notification(request):
    """Send a notification to students in instructor's courses."""
    allocated_courses = Course.objects.filter(assigned_instructor=request.user)

    # Build audience choices dynamically
    audience_choices = [('all', 'All my students')]
    for c in allocated_courses:
        audience_choices.append((str(c.pk), f'Students of {c.title}'))

    form = StaffNotificationForm()
    form.fields['audience'].choices = audience_choices

    if request.method == 'POST':
        form = StaffNotificationForm(request.POST)
        form.fields['audience'].choices = audience_choices
        if form.is_valid():
            title = form.cleaned_data['title']
            message = form.cleaned_data['message']
            audience = form.cleaned_data['audience']

            if audience == 'all':
                courses_to_notify = allocated_courses
            else:
                courses_to_notify = allocated_courses.filter(pk=audience)

            student_ids = set()
            for course in courses_to_notify:
                ids = course.enrollments.filter(status='active').values_list('student_id', flat=True)
                student_ids.update(ids)

            from accounts.models import User as UserModel
            from notifications.utils import create_notification
            students = UserModel.objects.filter(pk__in=student_ids)
            for student in students:
                create_notification(
                    recipient=student,
                    notification_type='course',
                    title=title,
                    message=message,
                )

            messages.success(request, f'Notification sent to {students.count()} student(s).')
            return redirect('staff:send_notification')

    return render(request, 'staff/send_notification.html', {
        'form': form,
        'allocated_courses': allocated_courses,
    })


# ── Internal helper ───────────────────────────────────────────────
def _notify_course_students(course, title, message):
    """Create in-app + email notifications for all active students in a course."""
    from notifications.utils import create_notification
    enrollments = course.enrollments.filter(status='active').select_related('student')
    for enrollment in enrollments:
        create_notification(
            recipient=enrollment.student,
            notification_type='course',
            title=title,
            message=message,
        )