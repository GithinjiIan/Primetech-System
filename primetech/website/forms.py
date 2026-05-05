"""
Website forms — course application form for prospective students.
"""
from django import forms
from .models import CourseApplication


class CourseApplicationForm(forms.ModelForm):
    """Form for prospective students to apply for a course."""

    class Meta:
        model = CourseApplication
        fields = ['full_name', 'email', 'phone_number', 'nationality', 'gender', 'course', 'motivation']
        widgets = {
            'full_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Full name',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Email address',
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Phone number',
            }),
            'nationality': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nationality',
            }),
            'gender': forms.Select(attrs={
                'class': 'form-select',
            }),
            'course': forms.HiddenInput(),
            'motivation': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Why are you interested in this course?',
            }),
        }
