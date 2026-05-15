"""
LMS Core Models: CourseMaterial, Assignment, Submission, Grade, ClassSession.
These power the learning experience for students and content management for staff.
"""
from django.db import models
from django.conf import settings
from django.utils import timezone


class CourseMaterial(models.Model):
    """A unit of learning content (video, PDF, link, or rich-text) in a course."""

    TYPE_CHOICES = [
        ('text', 'Rich Text / Article'),
        ('video', 'Video (Embed URL)'),
        ('pdf', 'PDF Document'),
        ('file', 'File Download'),
        ('link', 'External Link'),
    ]

    course = models.ForeignKey(
        'website.Course',
        on_delete=models.CASCADE,
        related_name='materials',
    )
    title = models.CharField(max_length=255)
    material_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='text')
    description = models.TextField(blank=True, help_text="Short description visible on the material list")

    # Rich text content (for text-type materials)
    content = models.TextField(
        blank=True,
        help_text="Rich HTML content. Used when material_type is 'text'."
    )

    # File upload (for PDF/file types)
    file = models.FileField(
        upload_to='course_materials/%Y/%m/',
        blank=True, null=True,
        help_text="Upload a PDF or document file."
    )

    # URL (for video embed or external link)
    url = models.URLField(
        blank=True,
        help_text="Video embed URL or external resource link."
    )

    order = models.PositiveSmallIntegerField(default=0, help_text="Display order within the course")
    is_published = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_materials',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'created_at']
        verbose_name = 'Course Material'
        verbose_name_plural = 'Course Materials'

    def __str__(self):
        return f"[{self.get_material_type_display()}] {self.title} — {self.course.title}"


class MaterialProgress(models.Model):
    """Tracks whether a student has marked a material as complete."""
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='material_progress')
    material = models.ForeignKey(CourseMaterial, on_delete=models.CASCADE, related_name='progress_records')
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['student', 'material']

    def mark_complete(self):
        if not self.completed:
            self.completed = True
            self.completed_at = timezone.now()
            self.save(update_fields=['completed', 'completed_at'])


class ClassSession(models.Model):
    """A scheduled class session for a course."""

    MODE_CHOICES = [
        ('online', 'Online (Virtual)'),
        ('physical', 'Physical (In-person)'),
        ('hybrid', 'Hybrid'),
    ]

    course = models.ForeignKey(
        'website.Course',
        on_delete=models.CASCADE,
        related_name='sessions',
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    session_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default='online')
    location = models.CharField(
        max_length=255, blank=True,
        help_text="Room/venue for physical, or meeting link for online sessions"
    )
    meeting_link = models.URLField(blank=True, help_text="Zoom / Google Meet / Teams link")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_sessions',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['session_date', 'start_time']
        verbose_name = 'Class Session'
        verbose_name_plural = 'Class Sessions'

    def __str__(self):
        return f"{self.course.title} — {self.title} ({self.session_date})"

    @property
    def is_upcoming(self):
        return self.session_date >= timezone.now().date()


class Assignment(models.Model):
    """An assignment given to students in a course."""

    course = models.ForeignKey(
        'website.Course',
        on_delete=models.CASCADE,
        related_name='assignments',
    )
    title = models.CharField(max_length=255)
    instructions = models.TextField(
        help_text="Detailed instructions for the assignment. HTML supported."
    )
    max_score = models.PositiveSmallIntegerField(default=100)
    due_date = models.DateTimeField()
    allow_late_submission = models.BooleanField(default=False)
    attachment = models.FileField(
        upload_to='assignment_files/%Y/%m/',
        blank=True, null=True,
        help_text="Optional attachment (rubric, starter files, etc.)"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_assignments',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ['due_date']
        verbose_name = 'Assignment'
        verbose_name_plural = 'Assignments'

    def __str__(self):
        return f"{self.course.title} — {self.title}"

    @property
    def is_past_due(self):
        return timezone.now() > self.due_date

    @property
    def submissions_count(self):
        return self.submissions.count()

    @property
    def pending_grading_count(self):
        return self.submissions.filter(grade__isnull=True).count()


class Submission(models.Model):
    """A student's submission for an assignment."""

    STATUS_CHOICES = [
        ('submitted', 'Submitted'),
        ('graded', 'Graded'),
        ('returned', 'Returned for Revision'),
    ]

    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='submissions',
    )
    content = models.TextField(blank=True, help_text="Written answer or additional notes")
    file = models.FileField(
        upload_to='student_submissions/%Y/%m/',
        blank=True, null=True,
        help_text="Submission file (PDF, doc, zip, etc.)"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='submitted')
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-submitted_at']
        unique_together = ['assignment', 'student']
        verbose_name = 'Submission'
        verbose_name_plural = 'Submissions'

    def __str__(self):
        return f"{self.student.get_full_name()} → {self.assignment.title}"

    @property
    def is_late(self):
        return self.submitted_at > self.assignment.due_date


class Grade(models.Model):
    """Staff grade and feedback for a student submission."""

    submission = models.OneToOneField(Submission, on_delete=models.CASCADE, related_name='grade')
    score = models.DecimalField(max_digits=5, decimal_places=2)
    feedback = models.TextField(
        blank=True,
        help_text="Detailed feedback for the student. HTML supported."
    )
    graded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='graded_submissions',
    )
    graded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Grade'
        verbose_name_plural = 'Grades'

    def __str__(self):
        return f"{self.submission} — {self.score}/{self.submission.assignment.max_score}"

    @property
    def percentage(self):
        if self.submission.assignment.max_score:
            return round((float(self.score) / self.submission.assignment.max_score) * 100, 1)
        return 0

    @property
    def letter_grade(self):
        pct = self.percentage
        if pct >= 90: return 'A'
        if pct >= 80: return 'B'
        if pct >= 70: return 'C'
        if pct >= 60: return 'D'
        return 'F'
