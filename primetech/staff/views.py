"""
Staff views: course content management, sessions, assignments, grading, notifications.
"""
import json
import logging
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Count, Prefetch, Q
from django.views.decorators.http import require_POST
from website.models import Course, Enrollment
from accounts.decorators import staff_required
from notifications.models import Notification
from courses.models import CourseModule, CourseMaterial, CourseSyllabus, ClassSession, Assignment, Submission, Grade
from courses.forms import (
    CourseModuleForm, CourseMaterialForm, CourseSyllabusForm,
    ClassSessionForm, AssignmentForm, GradeForm, StaffNotificationForm
)

logger = logging.getLogger(__name__)


# ── Dashboard ─────────────────────────────────────────────────────────────────
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


# ── Course Allocation ─────────────────────────────────────────────────────────
@staff_required
def course_allocation(request):
    allocated_courses = Course.objects.filter(
        assigned_instructor=request.user
    ).annotate(students_count=Count('enrollments'))
    return render(request, 'staff/course_allocation.html', {'allocated_courses': allocated_courses})


# ── Students Roll Call ────────────────────────────────────────────────────────
@staff_required
def students_rollcall(request):
    allocated_courses = Course.objects.filter(
        assigned_instructor=request.user
    ).prefetch_related('enrollments__student')
    for course in allocated_courses:
        course.enrolled_students = course.enrollments.filter(status='active').select_related('student')
    return render(request, 'staff/students_rollcall.html', {'allocated_courses': allocated_courses})


# ── Course Content (Materials + Modules + Syllabus) ───────────────────────
@staff_required
def courses_setup(request):
    """
    Main course content page. Handles:
      - Module CRUD  (add_module / edit_module / delete_module)
      - Material CRUD (add_material / edit_material / delete_material)
      - Syllabus save (save_syllabus)
    Materials may be assigned to a module (grouped) or left flat (module=NULL).
    Deleting a module cascades and removes all its child materials.
    """
    allocated_courses = Course.objects.filter(assigned_instructor=request.user, is_active=True)
    selected_course   = None
    flat_materials    = []
    modules           = []
    syllabus          = None
    syllabus_form     = CourseSyllabusForm()
    material_form     = CourseMaterialForm()
    module_form       = CourseModuleForm()
    active_tab        = 'materials'
    show_material_modal = False
    show_module_modal   = False

    course_id = request.GET.get('course_id') or request.POST.get('course_id')
    if course_id:
        selected_course = get_object_or_404(Course, pk=course_id, assigned_instructor=request.user)

        flat_materials = (
            CourseMaterial.objects
            .filter(course=selected_course, module__isnull=True)
            .select_related('created_by')
            .order_by('order', 'created_at')
        )
        modules = (
            CourseModule.objects
            .filter(course=selected_course)
            .prefetch_related(
                Prefetch(
                    'materials',
                    queryset=CourseMaterial.objects
                        .select_related('created_by')
                        .order_by('order', 'created_at'),
                )
            )
            .order_by('order', 'created_at')
        )

        try:
            syllabus = selected_course.syllabus
        except CourseSyllabus.DoesNotExist:
            syllabus = None

        material_form = CourseMaterialForm(course=selected_course)
        syllabus_form = CourseSyllabusForm(instance=syllabus)

        # ── GET: pre-populate modals for editing ─────────────────────────
        if request.method == 'GET':
            edit_material_id = request.GET.get('edit_material')
            edit_module_id   = request.GET.get('edit_module')

            if edit_material_id:
                existing = get_object_or_404(CourseMaterial, pk=edit_material_id, course=selected_course)
                material_form = CourseMaterialForm(instance=existing, course=selected_course)
                show_material_modal = True

            elif edit_module_id:
                existing_mod = get_object_or_404(CourseModule, pk=edit_module_id, course=selected_course)
                module_form = CourseModuleForm(instance=existing_mod)
                show_module_modal = True

        # ── POST: handle all actions ──────────────────────────────────
        elif request.method == 'POST':
            action = request.POST.get('action')

            # ── Add module ────────────────────────────────────────────
            if action == 'add_module':
                module_form = CourseModuleForm(request.POST)
                if module_form.is_valid():
                    mod = module_form.save(commit=False)
                    mod.course     = selected_course
                    mod.created_by = request.user
                    mod.save()
                    if mod.is_published:
                        _notify_course_students(
                            selected_course,
                            title=f'New module: {mod.title}',
                            message=f'A new module has been published in "{selected_course.title}".',
                        )
                    messages.success(request, f'Module "{mod.title}" created.')
                    return redirect(f'{request.path}?course_id={selected_course.pk}&tab=materials')
                show_module_modal = True

            # ── Edit module ─────────────────────────────────────────
            elif action == 'edit_module':
                module_id    = request.POST.get('module_id')
                existing_mod = get_object_or_404(CourseModule, pk=module_id, course=selected_course)
                was_published = existing_mod.is_published
                module_form  = CourseModuleForm(request.POST, instance=existing_mod)
                if module_form.is_valid():
                    mod = module_form.save()
                    if mod.is_published and not was_published:
                        _notify_course_students(
                            selected_course,
                            title=f'Module published: {mod.title}',
                            message=f'"{mod.title}" is now available in "{selected_course.title}".',
                        )
                    messages.success(request, f'Module "{existing_mod.title}" updated.')
                    return redirect(f'{request.path}?course_id={selected_course.pk}&tab=materials')
                show_module_modal = True

            # ── Delete module (cascades to its materials) ───────────────
            elif action == 'delete_module':
                module_id = request.POST.get('module_id')
                mod = get_object_or_404(CourseModule, pk=module_id, course=selected_course)
                # Delete file attachments for any materials inside this module
                for mat in mod.materials.all():
                    if mat.file:
                        mat.file.delete(save=False)
                mod_title = mod.title
                mod.delete()  # CASCADE removes all child CourseMaterial rows
                messages.success(request, f'Module "{mod_title}" and all its materials have been deleted.')
                return redirect(f'{request.path}?course_id={selected_course.pk}&tab=materials')

            # ── Add material ─────────────────────────────────────────
            elif action == 'add_material':
                material_form = CourseMaterialForm(request.POST, request.FILES, course=selected_course)
                if material_form.is_valid():
                    mat            = material_form.save(commit=False)
                    mat.course     = selected_course
                    mat.created_by = request.user
                    mat.save()
                    if mat.is_published:
                        _notify_course_students(
                            selected_course,
                            title=f'New material: {mat.title}',
                            message=f'New learning material has been added to "{selected_course.title}".',
                        )
                    messages.success(request, f'Material "{mat.title}" added.')
                    return redirect(f'{request.path}?course_id={selected_course.pk}&tab=materials')
                show_material_modal = True

            # ── Edit material ───────────────────────────────────────
            elif action == 'edit_material':
                material_id = request.POST.get('material_id')
                existing    = get_object_or_404(CourseMaterial, pk=material_id, course=selected_course)
                was_published = existing.is_published
                material_form = CourseMaterialForm(
                    request.POST, request.FILES,
                    instance=existing,
                    course=selected_course,
                )
                if material_form.is_valid():
                    new_type = material_form.cleaned_data.get('material_type')
                    # Delete old file if a new one replaces it
                    if existing.file and request.FILES.get('file') and new_type in ('pdf', 'file'):
                        existing.file.delete(save=False)
                    mat = material_form.save(commit=False)
                    mat.course = selected_course
                    if not mat.created_by_id:
                        mat.created_by = existing.created_by
                    mat.save()
                    if mat.is_published and not was_published:
                        _notify_course_students(
                            selected_course,
                            title=f'Material published: {mat.title}',
                            message=f'"{mat.title}" is now available in "{selected_course.title}".',
                        )
                    messages.success(request, f'Material "{mat.title}" updated.')
                    return redirect(f'{request.path}?course_id={selected_course.pk}&tab=materials')
                show_material_modal = True

            # ── Delete material ──────────────────────────────────────
            elif action == 'delete_material':
                mat_id = request.POST.get('material_id')
                mat    = get_object_or_404(CourseMaterial, pk=mat_id, course=selected_course)
                if mat.file:
                    mat.file.delete(save=False)
                mat.delete()
                messages.success(request, 'Material deleted.')
                return redirect(f'{request.path}?course_id={selected_course.pk}&tab=materials')

            # ── Save syllabus ──────────────────────────────────────
            elif action == 'save_syllabus':
                syllabus_form = CourseSyllabusForm(request.POST, instance=syllabus)
                if syllabus_form.is_valid():
                    syl = syllabus_form.save(commit=False)
                    syl.course     = selected_course
                    syl.updated_by = request.user
                    syl.save()
                    _notify_course_students(
                        selected_course,
                        title=f'Syllabus updated: {selected_course.title}',
                        message=f'The course syllabus for "{selected_course.title}" has been updated.',
                    )
                    messages.success(request, 'Course syllabus saved successfully.')
                    return redirect(f'{request.path}?course_id={selected_course.pk}&tab=syllabus')
                active_tab = 'syllabus'

    # Honour tab GET param only when a course is selected
    if selected_course and request.GET.get('tab') == 'syllabus':
        active_tab = 'syllabus'

    return render(request, 'staff/courses_setup.html', {
        'allocated_courses': allocated_courses,
        'selected_course': selected_course,
        'flat_materials': flat_materials,
        'modules': modules,
        'material_form': material_form,
        'module_form': module_form,
        'syllabus_form': syllabus_form,
        'syllabus': syllabus,
        'active_tab': active_tab,
        'show_material_modal': show_material_modal,
        'show_module_modal': show_module_modal,
    })


@staff_required
@require_POST
def reorder_content(request):
    """
    AJAX view to handle drag-and-drop reordering of modules and materials.
    Payload: { "type": "module"|"material", "order": [{"id": pk, "order": int}, ...] }
    """
    try:
        from django.db import transaction
        with transaction.atomic():
            data = json.loads(request.body)
            item_type = data.get('type')
            orders = data.get('order', [])

            if item_type == 'module':
                for o in orders:
                    mod_id = o.get('id')
                    new_ord = o.get('order')
                    if mod_id is not None and new_ord is not None:
                        module = get_object_or_404(CourseModule, pk=mod_id, course__assigned_instructor=request.user)
                        module.order = new_ord
                        module.save(update_fields=['order'])
            elif item_type == 'material':
                for o in orders:
                    mat_id = o.get('id')
                    new_ord = o.get('order')
                    if mat_id is not None and new_ord is not None:
                        material = get_object_or_404(CourseMaterial, pk=mat_id, course__assigned_instructor=request.user)
                        material.order = new_ord
                        material.save(update_fields=['order'])
            else:
                return JsonResponse({'error': 'Invalid item type'}, status=400)

            return JsonResponse({'status': 'success'})
    except Exception as e:
        logger.exception("Error in reorder_content view", exc_info=True)
        return JsonResponse({'error': 'Unable to reorder items'}, status=400)


# ── Class Sessions ────────────────────────────────────────────────────────────
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
                    _notify_course_students(
                        course=selected_course,
                        title=f'New Session: {session.title}',
                        message=(
                            f'A new class session "{session.title}" has been scheduled for '
                            f'{session.session_date.strftime("%b %d, %Y")} at '
                            f'{session.start_time.strftime("%I:%M %p")}.'
                        ),
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


# ── Assignments ───────────────────────────────────────────────────────────────
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
                        message=(
                            f'A new assignment "{assignment.title}" has been posted in '
                            f'"{selected_course.title}". '
                            f'Due: {assignment.due_date.strftime("%b %d, %Y %I:%M %p")}.'
                        ),
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


# ── Student Submissions (grading) ─────────────────────────────────────────────
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
            # FIX #13: call full_clean() so Grade.clean() validates score
            # against max_score even for brand-new Grade objects where the
            # form's clean_score() cannot yet access the submission FK.
            grade.full_clean(exclude=['submission'])
            grade.save()
            submission.status = 'graded'
            submission.save(update_fields=['status'])

            from notifications.utils import create_notification
            create_notification(
                recipient=submission.student,
                notification_type='course',
                title=f'Assignment Graded: {submission.assignment.title}',
                message=(
                    f'Your submission for "{submission.assignment.title}" in '
                    f'"{submission.assignment.course.title}" has been graded. '
                    f'Score: {grade.score}/{submission.assignment.max_score}.'
                ),
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


# ── Staff Notifications ───────────────────────────────────────────────────────
@staff_required
def send_notification(request):
    """Send a notification to students in instructor's courses."""
    allocated_courses = Course.objects.filter(assigned_instructor=request.user)

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
            message_text = form.cleaned_data['message']
            audience = form.cleaned_data['audience']

            courses_to_notify = (
                allocated_courses if audience == 'all'
                else allocated_courses.filter(pk=audience)
            )

            student_ids = set()
            for course in courses_to_notify:
                ids = course.enrollments.filter(status='active').values_list('student_id', flat=True)
                student_ids.update(ids)

            from accounts.models import User as UserModel
            from notifications.utils import create_notification

            # FIX #7: materialise the queryset once so we can use len() rather
            # than issuing a second COUNT query after the notification loop.
            students = list(UserModel.objects.filter(pk__in=student_ids))
            for student in students:
                create_notification(
                    recipient=student,
                    notification_type='course',
                    title=title,
                    message=message_text,
                )

            messages.success(request, f'Notification sent to {len(students)} student(s).')
            return redirect('staff:send_notification')

    return render(request, 'staff/send_notification.html', {
        'form': form,
        'allocated_courses': allocated_courses,
    })


# ── Internal helper ───────────────────────────────────────────────────────────
def _notify_course_students(course, title, message):
    """Create in-app notifications for all active students in a course."""
    from notifications.utils import create_notification
    enrollments = course.enrollments.filter(status='active').select_related('student')
    for enrollment in enrollments:
        create_notification(
            recipient=enrollment.student,
            notification_type='course',
            title=title,
            message=message,
        )
