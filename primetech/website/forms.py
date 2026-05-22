"""
Website forms — course application form for prospective students.
"""
from django import forms
from .models import CourseApplication


class NewsletterSignupForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email',
            'required': True,
        })
    )


class NewsletterSendForm(forms.Form):
    TARGET_CHOICES = [
        ('subscribers', 'Newsletter Subscribers'),
        ('enrolled', 'Enrolled Students'),
        ('all_users', 'All Active Users'),
        ('subscribers_and_enrolled', 'Subscribers and Enrolled Students'),
    ]

    subject = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'vTextField', 'style': 'width: 60%;'}),
    )
    body = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'vLargeTextField', 'rows': 10}),
    )
    target = forms.ChoiceField(choices=TARGET_CHOICES)
    create_notifications = forms.BooleanField(
        required=False,
        initial=True,
        label='Create in-app notifications for users',
    )


class CourseApplicationForm(forms.ModelForm):
    """Form for prospective students to apply for a course."""

    class Meta:
        model = CourseApplication
        fields = ['full_name', 'email', 'phone_number', 'education_level', 'nationality', 'gender', 'employment_status', 'course', 'motivation']
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
            'education_level': forms.Select(attrs={
                'class': 'form-select',
            }),
            'nationality': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nationality',
            }),
            'gender': forms.Select(attrs={
                'class': 'form-select',
            }),
            'employment_status': forms.Select(attrs={
                'class': 'form-select',
            }),
            'course': forms.HiddenInput(),
            'motivation': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Why are you interested in this course?',
            }),
        }
