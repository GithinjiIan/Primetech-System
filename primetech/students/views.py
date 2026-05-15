"""
Student views: dashboard, enrolled courses, materials, sessions, submissions, profile.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import get_user_model
from django import forms as django_forms

from website.models import Enrollment, Course
from accounts.decorators import student_required
from notifications.models import Notification
from courses.models import CourseMaterial, ClassSession, Assignment, Submission, Grade, MaterialProgress
from courses.forms import SubmissionForm

User = get_user_model()


# ── Dashboard ────────────────────────────────────────────────────
@student_required
def student_dashboard(request):
    """Student dashboard: enrolled courses and notifications."""
    enrollments = Enrollment.objects.filter(
        student=request.user, status='active'
    ).select_related('course', 'course__category')

    notifications = Notification.objects.filter(
        recipient=request.user
    ).order_by('-created_at')[:10]

    # Pending assignments count
    enrolled_course_ids = enrollments.values_list('course_id', flat=True)
    pending_assignments = Assignment.objects.filter(
        course_id__in=enrolled_course_ids,
        is_published=True,
    ).exclude(submissions__student=request.user).count()

    return render(request, 'students/dashboard.html', {
        'enrollments': enrollments,
        'notifications': notifications,
        'pending_assignments': pending_assignments,
    })


# ── My Courses (enrolled only) ────────────────────────────────────
@student_required
def my_courses(request):
    """Show ONLY the courses this student is enrolled in."""
    enrollments = Enrollment.objects.filter(
        student=request.user, status='active'
    ).select_related('course', 'course__category', 'course__assigned_instructor')

    # Attach material + progress data per course
    for enrollment in enrollments:
        total = CourseMaterial.objects.filter(course=enrollment.course, is_published=True).count()
        completed = MaterialProgress.objects.filter(
            student=request.user,
            material__course=enrollment.course,
            completed=True,
        ).count()
        enrollment.total_materials = total
        enrollment.completed_materials = completed
        enrollment.progress_pct = int((completed / total) * 100) if total else 0

    return render(request, 'students/my_courses.html', {'enrollments': enrollments})


# ── Course Material Viewer ────────────────────────────────────────
@student_required
def course_materials(request, course_id):
    """View all published materials for an enrolled course."""
    course = get_object_or_404(Course, pk=course_id, is_active=True)

    # Verify enrollment
    enrollment = get_object_or_404(Enrollment, student=request.user, course=course, status='active')
    materials = CourseMaterial.objects.filter(course=course, is_published=True).order_by('order')

    # Fetch completed material IDs for this student
    completed_ids = set(
        MaterialProgress.objects.filter(
            student=request.user,
            material__course=course,
            completed=True,
        ).values_list('material_id', flat=True)
    )

    # Handle mark-as-complete toggle
    if request.method == 'POST':
        mat_id = request.POST.get('material_id')
        if mat_id:
            material = get_object_or_404(CourseMaterial, pk=mat_id, course=course)
            progress, _ = MaterialProgress.objects.get_or_create(
                student=request.user,
                material=material,
            )
            progress.mark_complete()
            messages.success(request, f'"{material.title}" marked as complete.')
        return redirect('students:course_materials', course_id=course_id)

    return render(request, 'students/course_materials.html', {
        'course': course,
        'materials': materials,
        'completed_ids': completed_ids,
        'enrollment': enrollment,
    })


# ── Single Material Detail ────────────────────────────────────────
@student_required
def material_detail(request, course_id, material_id):
    """View a single course material."""
    course = get_object_or_404(Course, pk=course_id, is_active=True)
    get_object_or_404(Enrollment, student=request.user, course=course, status='active')
    material = get_object_or_404(CourseMaterial, pk=material_id, course=course, is_published=True)

    progress, _ = MaterialProgress.objects.get_or_create(student=request.user, material=material)

    if request.method == 'POST':
        progress.mark_complete()
        messages.success(request, f'"{material.title}" marked as complete!')
        return redirect('students:course_materials', course_id=course_id)

    return render(request, 'students/material_detail.html', {
        'course': course,
        'material': material,
        'progress': progress,
    })


# ── Class Sessions ────────────────────────────────────────────────
@student_required
def student_sessions(request):
    """Show scheduled sessions for all enrolled courses."""
    enrolled_course_ids = Enrollment.objects.filter(
        student=request.user, status='active'
    ).values_list('course_id', flat=True)

    sessions = ClassSession.objects.filter(
        course_id__in=enrolled_course_ids
    ).select_related('course').order_by('session_date', 'start_time')

    return render(request, 'students/class_sessions.html', {'sessions': sessions})


# ── Assignments & Submissions ─────────────────────────────────────
@student_required
def student_submissions(request):
    """List all assignments for enrolled courses and submission status."""
    enrolled_course_ids = Enrollment.objects.filter(
        student=request.user, status='active'
    ).values_list('course_id', flat=True)

    assignments = Assignment.objects.filter(
        course_id__in=enrolled_course_ids,
        is_published=True,
    ).select_related('course').order_by('due_date')

    # Map assignment_id -> submission
    my_submissions = {
        sub.assignment_id: sub
        for sub in Submission.objects.filter(student=request.user).select_related('grade')
    }

    for assignment in assignments:
        assignment.my_submission = my_submissions.get(assignment.pk)

    return render(request, 'students/student_submissions.html', {
        'assignments': assignments,
    })


@student_required
def submit_assignment(request, assignment_id):
    """Submit or resubmit work for an assignment."""
    enrolled_course_ids = Enrollment.objects.filter(
        student=request.user, status='active'
    ).values_list('course_id', flat=True)

    assignment = get_object_or_404(
        Assignment,
        pk=assignment_id,
        course_id__in=enrolled_course_ids,
        is_published=True,
    )

    existing = Submission.objects.filter(assignment=assignment, student=request.user).first()

    if request.method == 'POST':
        form = SubmissionForm(request.POST, request.FILES, instance=existing)
        if form.is_valid():
            sub = form.save(commit=False)
            sub.assignment = assignment
            sub.student = request.user
            sub.status = 'submitted'
            sub.save()
            messages.success(request, f'Your submission for "{assignment.title}" was received!')
            return redirect('students:submissions')
    else:
        form = SubmissionForm(instance=existing)

    return render(request, 'students/submit_assignment.html', {
        'assignment': assignment,
        'form': form,
        'existing': existing,
    })


# ── Student Profile ───────────────────────────────────────────────
class StudentProfileForm(django_forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone_number', 'nationality', 'gender', 'bio', 'profile_picture']
        widgets = {
            'first_name': django_forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': django_forms.TextInput(attrs={'class': 'form-control'}),
            'phone_number': django_forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+254 700 000000'}),
            'nationality': django_forms.TextInput(attrs={'class': 'form-control'}),
            'gender': django_forms.Select(attrs={'class': 'form-select'}),
            'bio': django_forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Tell us a bit about yourself…'}),
            'profile_picture': django_forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }


@student_required
def student_profile(request):
    """View and edit student profile."""
    if request.method == 'POST':
        form = StudentProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('students:student_profile')
    else:
        form = StudentProfileForm(instance=request.user)

    enrollments = Enrollment.objects.filter(
        student=request.user, status='active'
    ).select_related('course')

    return render(request, 'students/student_profile.html', {
        'form': form,
        'enrollments': enrollments,
    })


# ── Course Enroll (public application redirect) ───────────────────
@student_required
def course_enroll(request):
    """Redirect student to the public courses page to apply."""
    return redirect('courses')