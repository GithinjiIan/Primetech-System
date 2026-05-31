"""
Student views: dashboard, enrolled courses, materials, sessions, submissions, profile.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import get_user_model
from django import forms as django_forms
from django.core.paginator import Paginator
from django.utils import timezone

from website.models import Enrollment, Course
from accounts.decorators import student_required
from notifications.models import Notification
from courses.models import (
    CourseMaterial, CourseSyllabus, ClassSession,
    Assignment, Submission, Grade, MaterialProgress,
)
from courses.forms import SubmissionForm
import re

User = get_user_model()

# Materials shown per page on the course_materials view
MATERIALS_PER_PAGE = 9


# ── Dashboard ────────────────────────────────────────────────────
@student_required
def student_dashboard(request):
    """Student dashboard: enrolled courses and notifications."""
    enrollments = Enrollment.objects.filter(
        student=request.user, status='active'
    ).select_related('course', 'course__category')

    notifications = Notification.objects.filter(
        recipient=request.user,
        is_archived=False,
    ).order_by('-created_at')[:10]

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


@student_required
def student_notifications(request):
    """Student notification center page for current user's active notifications."""
    notifications = Notification.objects.filter(
        recipient=request.user,
        is_archived=False,
    ).order_by('-created_at')
    return render(request, 'students/notifications.html', {
        'notifications': notifications,
    })


@student_required
def student_notification_detail(request, pk):
    """Show a single notification detail and mark it as read."""
    notification = get_object_or_404(
        Notification,
        pk=pk,
        recipient=request.user,
        is_archived=False,
    )
    if not notification.is_read:
        notification.mark_as_read()
    return render(request, 'students/notification_detail.html', {
        'notification': notification,
    })


# ── My Courses (enrolled only) ────────────────────────────────────
@student_required
def my_courses(request):
    """Show ONLY the courses this student is enrolled in."""
    enrollments = Enrollment.objects.filter(
        student=request.user, status='active'
    ).select_related('course', 'course__category', 'course__assigned_instructor')

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
    """
    View all published materials for an enrolled course, with:
      - Course syllabus shown as a collapsible section above the material cards
      - Materials paginated (MATERIALS_PER_PAGE per page)
      - Mark-as-complete POST action
    """
    course = get_object_or_404(Course, pk=course_id, is_active=True)
    enrollment = get_object_or_404(Enrollment, student=request.user, course=course, status='active')

    # ── Handle mark-as-complete POST ────────────────────────────
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

    # ── Fetch materials + completed set ─────────────────────────
    all_materials = CourseMaterial.objects.filter(course=course, is_published=True).order_by('order')

    completed_ids = set(
        MaterialProgress.objects.filter(
            student=request.user,
            material__course=course,
            completed=True,
        ).values_list('material_id', flat=True)
    )

    # ── Pagination ───────────────────────────────────────────────
    paginator = Paginator(all_materials, MATERIALS_PER_PAGE)
    page_number = request.GET.get('page', 1)
    materials_page = paginator.get_page(page_number)

    # ── Syllabus (may not exist yet) ─────────────────────────────
    try:
        syllabus = course.syllabus
    except CourseSyllabus.DoesNotExist:
        syllabus = None

    # ── Overall progress stats ───────────────────────────────────
    total_count = all_materials.count()
    completed_count = len(completed_ids)
    progress_pct = int((completed_count / total_count) * 100) if total_count else 0

    return render(request, 'students/course_materials.html', {
        'course': course,
        'materials': materials_page,          # paginated
        'completed_ids': completed_ids,
        'enrollment': enrollment,
        'syllabus': syllabus,
        'total_count': total_count,
        'completed_count': completed_count,
        'progress_pct': progress_pct,
        'paginator': paginator,
    })


# ── Single Material Detail ────────────────────────────────────────
@student_required
def material_detail(request, course_id, material_id):
    """View a single course material."""
    course = get_object_or_404(Course, pk=course_id, is_active=True)
    get_object_or_404(Enrollment, student=request.user, course=course, status='active')
    material = get_object_or_404(CourseMaterial, pk=material_id, course=course, is_published=True)

    progress, _ = MaterialProgress.objects.get_or_create(student=request.user, material=material)

    # ── Previous / Next navigation ───────────────────────────────
    all_materials = list(
        CourseMaterial.objects.filter(course=course, is_published=True).order_by('order').values_list('pk', flat=True)
    )
    current_index = all_materials.index(material.pk) if material.pk in all_materials else -1
    prev_material_id = all_materials[current_index - 1] if current_index > 0 else None
    next_material_id = all_materials[current_index + 1] if current_index < len(all_materials) - 1 else None

    if request.method == 'POST':
        progress.mark_complete()
        messages.success(request, f'"{material.title}" marked as complete!')
        # Go to next material if available, else back to list
        if next_material_id:
            return redirect('students:material_detail', course_id=course_id, material_id=next_material_id)
        return redirect('students:course_materials', course_id=course_id)

    # ── Server-side pagination for long text materials ─────────
    page_content = None
    total_pages = 1
    try:
        current_page = int(request.GET.get('page', 1))
    except (TypeError, ValueError):
        current_page = 1

    if material.material_type == 'text' and material.content:
        html = material.content

        # Explicit page markers take precedence if the instructor inserts <!--page-->
        marker_pages = [part.strip() for part in re.split(r'<!--\s*page\s*-->', html, flags=re.IGNORECASE) if part.strip()]
        if len(marker_pages) > 1:
            pages = marker_pages
        else:
            # Split HTML into tokens by block-level closing tags to preserve structure roughly
            parts = re.split(r'(</(?:p|h[1-6]|ul|ol|li|blockquote|pre|table|figure|div)>)', html, flags=re.IGNORECASE)
            # Recombine delimiters with their preceding part
            tokens = []
            i = 0
            while i < len(parts):
                part = parts[i]
                if i + 1 < len(parts):
                    part += parts[i+1]
                    i += 2
                else:
                    i += 1
                if part.strip():
                    tokens.append(part)

            # Accumulate tokens into pages by approximate character threshold
            THRESHOLD = 2200
            pages = []
            cur = ''
            for tok in tokens:
                tok_text = re.sub('<[^<]+?>', '', tok).strip()
                if len(re.sub('<[^<]+?>', '', cur)) + len(tok_text) > THRESHOLD and cur:
                    pages.append(cur)
                    cur = tok
                else:
                    cur += tok
            if cur:
                pages.append(cur)

        if pages:
            total_pages = len(pages)
            if current_page < 1: current_page = 1
            if current_page > total_pages: current_page = total_pages
            page_content = pages[current_page - 1]

    # ── Precompute embed URL for video materials (handles common YouTube/Vimeo forms)
    embed_url = None
    if material.material_type == 'video' and material.url:
        url = material.url.strip()
        # YouTube watch URLs
        m = re.search(r'(?:v=|/v/|youtu\.be/)([\w-]{6,})', url)
        if m:
            vid = m.group(1)
            embed_url = f'https://www.youtube.com/embed/{vid}'
        else:
            # Vimeo patterns
            m2 = re.search(r'vimeo\.com/(?:video/)?(\d+)', url)
            if m2:
                vid = m2.group(1)
                embed_url = f'https://player.vimeo.com/video/{vid}'
            else:
                embed_url = url

    return render(request, 'students/material_detail.html', {
        'course': course,
        'material': material,
        'progress': progress,
        'prev_material_id': prev_material_id,
        'next_material_id': next_material_id,
        'total_in_course': len(all_materials),
        'current_position': current_index + 1,
        'page_content': page_content,
        'total_pages': total_pages,
        'current_page': current_page,
        'embed_url': embed_url,
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
        if assignment.is_past_due and not assignment.allow_late_submission:
            messages.error(request, 'The deadline for this assignment has passed and late submissions are not allowed.')
            return redirect('students:student_submissions')

        form = SubmissionForm(request.POST, request.FILES, instance=existing)
        if form.is_valid():
            old_file = None
            if existing and existing.file and 'file' in form.changed_data:
                # Defer deletion until after successful save
                old_file = existing.file

            sub = form.save(commit=False)
            sub.assignment = assignment
            sub.student = request.user
            sub.status = 'submitted'
            sub.save()
            
            # Delete old file only after successful DB commit
            if old_file:
                old_file.delete(save=False)
            
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