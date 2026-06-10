"""
Forms for LMS course content management (staff) and student submissions.
"""
import re
try:
    import nh3
    _SANITISER = 'nh3'
except ImportError:
    try:
        import bleach
        _SANITISER = 'bleach'
    except ImportError:
        _SANITISER = None

from django import forms
from django.core.exceptions import ValidationError
from django_ckeditor_5.widgets import CKEditor5Widget
from .models import CourseModule, CourseMaterial, CourseSyllabus, ClassSession, Assignment, Submission, Grade


# ── HTML sanitisation helper ──────────────────────────────────────────────────
# Strips any tags / attributes not in the allow-list before rich-text fields
# are stored.  Requires either `nh3` (preferred) or `bleach` to be installed.
# If neither is available the raw value is stored (staff-only forms so risk is
# lower, but installation of nh3 is strongly recommended: pip install nh3).

_ALLOWED_TAGS = {
    'p', 'br', 'strong', 'em', 'u', 's', 'del',
    'h2', 'h3', 'h4', 'h5',
    'ul', 'ol', 'li',
    'blockquote', 'pre', 'code',
    'table', 'thead', 'tbody', 'tfoot', 'tr', 'th', 'td',
    'a', 'img',
    'oembed',
    'figure', 'figcaption',
    'div', 'span',
    'hr',
    # CKEditor media-embed wrapper
    'iframe',
}

_ALLOWED_ATTRS = {
    'a':      ['href', 'title', 'target', 'rel'],
    'img':    ['src', 'alt', 'width', 'height', 'style', 'class', 'srcset', 'sizes'],
    'iframe': ['src', 'width', 'height', 'frameborder', 'allowfullscreen',
               'allow', 'title', 'style'],
    'oembed': ['url'],
    'td':     ['colspan', 'rowspan', 'style'],
    'th':     ['colspan', 'rowspan', 'style'],
    'div':    ['style', 'class'],
    'span':   ['style', 'class'],
    'p':      ['style', 'class'],
    'figure': ['class'],
    'table':  ['class', 'style'],
}


def _sanitise_html(value: str) -> str:
    """Return sanitised HTML, or the raw value if no sanitiser is installed."""
    if not value:
        return value
    if _SANITISER == 'nh3':
        return nh3.clean(
            value,
            tags=_ALLOWED_TAGS,
            attributes=_ALLOWED_ATTRS,
            link_rel=None,          # keep existing rel attributes
        )
    if _SANITISER == 'bleach':
        # bleach uses a list-based API
        allowed_tags = list(_ALLOWED_TAGS)
        allowed_attrs = {k: list(v) for k, v in _ALLOWED_ATTRS.items()}
        return bleach.clean(value, tags=allowed_tags, attributes=allowed_attrs, strip=True)
    # Fallback — no sanitiser installed; store as-is (log a warning in production)
    return value


# ── CKEditor widget helper ────────────────────────────────────────────────────
class CKEditorWidget(CKEditor5Widget):
    """Project wrapper around django-ckeditor-5's full WYSIWYG widget."""
    def __init__(self, editor_id, *args, **kwargs):
        attrs = kwargs.pop('attrs', {})
        attrs.update({
            'class': 'django_ckeditor_5 form-control',
            'id': editor_id,
        })
        super().__init__(config_name='course_full', attrs=attrs)

    def render(self, name, value, attrs=None, renderer=None):
        attrs = {} if attrs is None else dict(attrs)
        attrs.setdefault('id', self.attrs.get('id'))
        return super().render(name, value, attrs=attrs, renderer=renderer)


# ── CourseModuleForm ─────────────────────────────────────────────────────────

class CourseModuleForm(forms.ModelForm):
    """
    Staff form to create/edit a course module.
    Each module can have a rich-text notes body written by the instructor.
    """

    class Meta:
        model = CourseModule
        fields = ['title', 'description', 'notes', 'order', 'is_published']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'id': 'mod_title',
                'placeholder': "Module title, e.g. 'Module 1: Introduction'",
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'id': 'mod_description',
                'rows': 2,
                'placeholder': 'Short description of this module (optional)',
            }),
            'notes': CKEditorWidget('mod_notes', attrs={
                'rows': 12,
                'placeholder': 'Write module notes here…',
            }),
            'order': forms.NumberInput(attrs={
                'class': 'form-control',
                'id': 'mod_order',
                'min': 0,
            }),
            'is_published': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'mod_is_published',
            }),
        }
        labels = {
            'title': 'Module Title',
            'description': 'Short Description',
            'notes': 'Module Notes',
            'order': 'Display Order',
            'is_published': 'Publish immediately (visible to students)',
        }

    def clean_notes(self):
        notes = self.cleaned_data.get('notes', '')
        return _sanitise_html(notes) if notes else notes


# ── CourseMaterialForm ────────────────────────────────────────────────────────

class CourseMaterialForm(forms.ModelForm):
    """
    Staff form to add/edit course materials.
    Accepts a ``course`` keyword argument to populate the module dropdown
    with only the modules belonging to that course.
    """

    def __init__(self, *args, course=None, **kwargs):
        super().__init__(*args, **kwargs)
        if course is not None:
            self.fields['module'].queryset = CourseModule.objects.filter(course=course)
        else:
            self.fields['module'].queryset = CourseModule.objects.none()
        self.fields['module'].required = False
        self.fields['module'].empty_label = '— No module (flat material) —'

    class Meta:
        model = CourseMaterial
        fields = [
            'title', 'material_type', 'module',
            'description', 'content', 'file', 'url',
            'order', 'is_published',
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'id': 'mat_title',
                'placeholder': 'Material title',
            }),
            'material_type': forms.Select(attrs={
                'class': 'form-select',
                'id': 'mat_type',
            }),
            'module': forms.Select(attrs={
                'class': 'form-select',
                'id': 'mat_module',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'id': 'mat_description',
                'rows': 2,
                'placeholder': 'Brief description visible to students',
            }),
            # CKEditor for rich-text notes content
            'content': CKEditorWidget('materialContentEditor', attrs={
                'rows': 10,
                'placeholder': 'Write your notes here…',
            }),
            'file': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'id': 'mat_file',
            }),
            'url': forms.URLInput(attrs={
                'class': 'form-control',
                'id': 'mat_url',
                'placeholder': 'https://www.youtube.com/watch?v=… or https://…',
            }),
            'order': forms.NumberInput(attrs={
                'class': 'form-control',
                'id': 'mat_order',
                'min': 0,
            }),
            'is_published': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'mat_is_published',
            }),
        }
        labels = {
            'module': 'Assign to Module',
        }

    def clean(self):
        cleaned_data = super().clean()
        material_type = cleaned_data.get('material_type')
        content = cleaned_data.get('content', '')
        file_field = cleaned_data.get('file')
        url = (cleaned_data.get('url') or '').strip()
        cleaned_data['url'] = url

        if material_type == 'text':
            if not content or not content.strip():
                self.add_error('content', 'Please enter content for text materials.')
            else:
                # Sanitise rich HTML before storage
                cleaned_data['content'] = _sanitise_html(content)
            # Clear irrelevant fields; also delete the stored file if type changed
            cleaned_data['url'] = ''
            cleaned_data['file'] = self._maybe_delete_existing_file(file_field)

        elif material_type == 'video':
            if not url:
                self.add_error('url', 'Please provide a URL for this material type.')
            elif not self._is_video_url(url):
                self.add_error('url', 'Enter a valid YouTube or Vimeo URL (including Shorts).')
            cleaned_data['content'] = ''
            cleaned_data['file'] = self._maybe_delete_existing_file(file_field)

        elif material_type == 'link':
            if not url:
                self.add_error('url', 'Please provide a URL for this material type.')
            cleaned_data['content'] = ''
            cleaned_data['file'] = self._maybe_delete_existing_file(file_field)

        elif material_type in ('pdf', 'file'):
            if not file_field and not self._instance_has_file() and 'file' not in self.errors:
                self.add_error('file', 'Please upload a file for this material type.')
            cleaned_data['content'] = ''
            cleaned_data['url'] = ''

        return cleaned_data

    # ── helpers ──────────────────────────────────────────────────────────────

    def _instance_has_file(self):
        """True if the *existing* model instance already has a file saved."""
        return bool(self.instance and self.instance.pk and self.instance.file)

    def _maybe_delete_existing_file(self, new_file_value):
        """
        When the material type changes away from pdf/file, delete the orphaned
        file from storage and return None so the DB field is also cleared.
        """
        if self.instance and self.instance.pk and self.instance.file:
            self.instance.file.delete(save=False)
            self.instance.file = None
        return None

    @staticmethod
    def _is_video_url(url):
        """
        Returns True if *url* looks like a YouTube or Vimeo URL.
        This is an intentional *prefix* match (re.match anchors at the start).
        The JS buildVideoEmbedUrl() uses the same pattern set so both layers
        agree on what is considered a valid video URL.
        """
        return bool(re.match(
            r'(?:https?:\/\/)?(?:www\.)?(?:'
            r'youtube\.com\/(?:watch\?v=|embed\/|shorts\/)|'
            r'youtu\.be\/|'
            r'vimeo\.com\/(?:video\/)?|'
            r'player\.vimeo\.com\/video\/)'
            r'([\w-]+)',
            url or '',
            re.I,
        ))

    def clean_file(self):
        file = self.cleaned_data.get('file')
        # Read material_type from raw POST data because field-level clean_*
        # methods run before the form-level clean(), so material_type may not
        # yet be present in self.cleaned_data.
        material_type = self.data.get('material_type')
        if file and material_type in ('pdf', 'file'):
            valid_extensions = ['.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx', '.zip']
            filename = file.name.lower()
            if not any(filename.endswith(ext) for ext in valid_extensions):
                raise ValidationError(
                    'Upload a PDF, Word, PowerPoint, Excel, or ZIP document only.'
                )
        return file


# ── CourseSyllabusForm ────────────────────────────────────────────────────────

class CourseSyllabusForm(forms.ModelForm):
    """
    Staff form to create/update the structured syllabus for a course.
    Every rich-text section uses CKEditor (wired in the template).
    HTML is sanitised on save.
    """

    class Meta:
        model = CourseSyllabus
        fields = [
            'instructor_intro',
            'learning_outcomes',
            'course_relevance',
            'course_activities',
            'modules_overview',
            'final_project',
            'certification_info',
        ]
        widgets = {
            'instructor_intro': CKEditorWidget('syllabusInstructorIntro', attrs={
                'rows': 6,
                'placeholder': 'Introduce yourself and welcome students…',
            }),
            'learning_outcomes': CKEditorWidget('syllabusLearningOutcomes', attrs={
                'rows': 6,
                'placeholder': 'By the end of this course, students will be able to…',
            }),
            'course_relevance': CKEditorWidget('syllabusCourseRelevance', attrs={
                'rows': 6,
                'placeholder': 'Why is this course important? Industry trends, career impact…',
            }),
            'course_activities': CKEditorWidget('syllabusCourseActivities', attrs={
                'rows': 6,
                'placeholder': 'Readings, quizzes, group projects, live sessions…',
            }),
            'modules_overview': CKEditorWidget('syllabusModulesOverview', attrs={
                'rows': 10,
                'placeholder': 'Module 1: Introduction…\nModule 2: …',
            }),
            'final_project': CKEditorWidget('syllabusFinalProject', attrs={
                'rows': 6,
                'placeholder': 'Describe the capstone project, deliverables, and grading criteria…',
            }),
            'certification_info': CKEditorWidget('syllabusCertification', attrs={
                'rows': 6,
                'placeholder': 'Certificate name, issuing body, requirements to earn it…',
            }),
        }
        labels = {
            'instructor_intro': 'Instructor Introduction',
            'learning_outcomes': 'Learning Outcomes',
            'course_relevance': 'Course Relevance',
            'course_activities': 'Course Activities',
            'modules_overview': 'Overview of Course Modules',
            'final_project': 'Final Project',
            'certification_info': 'Certification',
        }

    def clean(self):
        cleaned_data = super().clean()
        # Sanitise every rich-text field before storage
        rich_fields = [
            'instructor_intro', 'learning_outcomes', 'course_relevance',
            'course_activities', 'modules_overview', 'final_project',
            'certification_info',
        ]
        for field in rich_fields:
            if cleaned_data.get(field):
                cleaned_data[field] = _sanitise_html(cleaned_data[field])
        return cleaned_data


# ── ClassSessionForm ──────────────────────────────────────────────────────────

class ClassSessionForm(forms.ModelForm):
    """Staff form to schedule a class session."""

    class Meta:
        model = ClassSession
        fields = ['title', 'description', 'session_date', 'start_time', 'end_time', 'mode', 'location', 'meeting_link']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Session title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'session_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'mode': forms.Select(attrs={'class': 'form-select'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Room / Venue name'}),
            'meeting_link': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://meet.google.com/...'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_time')
        end = cleaned_data.get('end_time')
        if start and end and end <= start:
            self.add_error('end_time', 'End time must be after start time.')
        return cleaned_data


# ── AssignmentForm ────────────────────────────────────────────────────────────

class AssignmentForm(forms.ModelForm):
    """Staff form to create/edit an assignment."""

    class Meta:
        model = Assignment
        fields = ['title', 'instructions', 'max_score', 'due_date', 'allow_late_submission', 'attachment', 'is_published']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Assignment title'}),
            'instructions': forms.Textarea(attrs={
                'class': 'form-control django-ckeditor',
                'rows': 8,
                'id': 'assignmentInstructions',
            }),
            'max_score': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'due_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'allow_late_submission': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'attachment': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


# ── GradeForm ─────────────────────────────────────────────────────────────────

class GradeForm(forms.ModelForm):
    """Staff form to grade a student submission."""

    class Meta:
        model = Grade
        fields = ['score', 'feedback']
        widgets = {
            'score': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5', 'min': 0}),
            'feedback': forms.Textarea(attrs={
                'class': 'form-control django-ckeditor',
                'rows': 6,
                'id': 'gradeFeedback',
            }),
        }

    def clean_score(self):
        score = self.cleaned_data.get('score')
        if score is None:
            return score
        if score < 0:
            raise ValidationError('Score cannot be negative.')
        # Access the related submission's max_score.
        # self.instance is the Grade object; it carries submission via its FK
        # when updating an existing grade.  For a brand-new grade the submission
        # is set in the view with grade.submission = submission before save(),
        # so we read it from the view-supplied kwarg if present.
        submission = getattr(self.instance, 'submission', None)
        if submission is not None:
            max_score = submission.assignment.max_score
            if score > max_score:
                raise ValidationError(
                    f'Score ({score}) cannot exceed the assignment maximum of {max_score}.'
                )
        return score


# ── SubmissionForm ────────────────────────────────────────────────────────────

class SubmissionForm(forms.ModelForm):
    """Student form to submit work for an assignment."""

    class Meta:
        model = Submission
        fields = ['content', 'file']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Write your answer or additional notes here…',
            }),
            'file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        content = (cleaned_data.get('content') or '').strip()
        file_field = cleaned_data.get('file')
        if not content and not file_field:
            raise ValidationError('Please provide either a written answer or upload a file.')
        return cleaned_data


# ── StaffNotificationForm ─────────────────────────────────────────────────────

class StaffNotificationForm(forms.Form):
    """Staff form to send a notification to students in a course."""

    AUDIENCE_CHOICES = [('all', 'All my students')]

    title = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Notification title'})
    )
    message = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Write your message…'})
    )
    audience = forms.ChoiceField(
        choices=AUDIENCE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
