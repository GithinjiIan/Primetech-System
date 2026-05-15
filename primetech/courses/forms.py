"""
Forms for LMS course content management (staff) and student submissions.
"""
from django import forms
from .models import CourseMaterial, ClassSession, Assignment, Submission, Grade


class CourseMaterialForm(forms.ModelForm):
    """Staff form to add/edit course materials."""

    class Meta:
        model = CourseMaterial
        fields = ['title', 'material_type', 'description', 'content', 'file', 'url', 'order', 'is_published']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Material title'}),
            'material_type': forms.Select(attrs={'class': 'form-select', 'id': 'materialTypeSelect'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Brief description visible to students'}),
            'content': forms.Textarea(attrs={'class': 'form-control django-ckeditor', 'rows': 8, 'id': 'materialContent'}),
            'file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


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


class AssignmentForm(forms.ModelForm):
    """Staff form to create/edit an assignment."""

    class Meta:
        model = Assignment
        fields = ['title', 'instructions', 'max_score', 'due_date', 'allow_late_submission', 'attachment', 'is_published']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Assignment title'}),
            'instructions': forms.Textarea(attrs={'class': 'form-control django-ckeditor', 'rows': 8, 'id': 'assignmentInstructions'}),
            'max_score': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'due_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'allow_late_submission': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'attachment': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class GradeForm(forms.ModelForm):
    """Staff form to grade a student submission."""

    class Meta:
        model = Grade
        fields = ['score', 'feedback']
        widgets = {
            'score': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5', 'min': 0}),
            'feedback': forms.Textarea(attrs={'class': 'form-control django-ckeditor', 'rows': 6, 'id': 'gradeFeedback'}),
        }


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
