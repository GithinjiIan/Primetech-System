from django.shortcuts import render, redirect, get_object_or_404
import json
from .models import Course, CourseCategory, Testimonial, Statistic, CourseApplication, NewsletterSubscriber
from .forms import CourseApplicationForm, NewsletterSignupForm
from django.contrib import messages
from django.views.decorators.http import require_POST


def newsletter_signup(request):
    if request.method == 'POST':
        form = NewsletterSignupForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email'].lower()
            subscriber, created = NewsletterSubscriber.objects.get_or_create(
                email=email,
                defaults={
                    'user': request.user if request.user.is_authenticated else None,
                    'first_name': request.user.first_name if request.user.is_authenticated else '',
                    'last_name': request.user.last_name if request.user.is_authenticated else '',
                    'is_active': True,
                }
            )
            if not created and not subscriber.is_active:
                subscriber.is_active = True
                subscriber.save(update_fields=['is_active'])
                messages.success(request, 'Welcome back! Your newsletter subscription is reactivated.')
            elif created:
                messages.success(request, 'Thank you for subscribing! You will receive our newsletter updates via email.')
                from notifications.tasks import send_newsletter_subscription_email
                send_newsletter_subscription_email.delay(subscriber.id)
            else:
                messages.info(request, 'You are already subscribed to the newsletter.')
        else:
            messages.error(request, 'Please enter a valid email address to subscribe.')
    return redirect('home')


def home_view(request):
    statistics = Statistic.objects.all()
    testimonials = Testimonial.objects.filter(is_active=True)
    latest_courses = Course.objects.filter(is_active=True).order_by('-created_at')[:3]
    context = {
        'statistics': statistics,
        'testimonials': testimonials,
        'latest_courses': latest_courses,
    }
    return render(request, 'website/home.html', context)

def about(request):
    """Render the about page."""
    return render(request, 'website/about.html')

def contact(request):
    """Render the contact page."""
    return render(request, 'website/contact.html')

def partnership(request):
    """Render the courses page."""
    return render(request, 'website/partnership.html')

"""COURSES PAGE VIEWS"""
def _build_courses_context(category_slug=None, application_form=None, selected_course_id=None, selected_course_title=None):
    courses = Course.objects.filter(is_active=True).select_related('category')
    if category_slug:
        courses = courses.filter(category__slug=category_slug)

    categories = CourseCategory.objects.all()
    testimonials = Testimonial.objects.filter(is_active=True)

    # Serialize course data to JSON for JavaScript detail population
    courses_dict = {}
    for course in courses:
        requirements = [item.strip() for item in course.requirements.splitlines() if item.strip()]
        outcomes = [item.strip() for item in course.outcomes.splitlines() if item.strip()]
        courses_dict[str(course.id)] = {
            'title': course.title,
            'description': course.description,
            'duration': course.duration,
            'schedule': course.schedule,
            'instructor': course.instructor,
            'price': course.price,
            'level': course.get_level_display(),
            'requirements': requirements,
            'outcomes': outcomes,
        }

    if application_form is None:
        application_form = CourseApplicationForm()

    return {
        'courses': courses,
        'categories': categories,
        'testimonials': testimonials,
        'courses_json': json.dumps(courses_dict),
        'application_form': application_form,
        'selected_course_id': selected_course_id,
        'selected_course_title': selected_course_title,
    }


#  views for the courses page

def courses(request):
    """Display courses filtered by optional category query parameter."""
    category_slug = request.GET.get('category', None)
    context = _build_courses_context(category_slug=category_slug)
    return render(request, 'website/courses.html', context)


@require_POST
def apply_for_course(request, course_id):
    """Handle course application submission from the website."""
    course = get_object_or_404(Course, pk=course_id, is_active=True)

    form = CourseApplicationForm(request.POST)
    if form.is_valid():
        application = form.save(commit=False)
        application.course = course
        application.save()

        # Notify admins
        from notifications.utils import create_notification
        from django.contrib.auth import get_user_model
        User = get_user_model()
        admins = User.objects.filter(role='superadmin', is_active=True)
        for admin_user in admins:
            create_notification(
                recipient=admin_user,
                notification_type='application',
                title=f'New Application: {course.title}',
                message=f'{application.full_name} ({application.email}) has applied for '
                        f'"{course.title}". Please review the application.',
            )

        messages.success(
            request,
            'Your application has been submitted successfully! '
            'We will review it and get back to you soon.'
        )
        return redirect('courses')

    messages.error(request, 'Please correct the errors below.')
    category_slug = request.GET.get('category', None)
    context = _build_courses_context(
        category_slug=category_slug,
        application_form=form,
        selected_course_id=course.id,
        selected_course_title=course.title,
    )
    return render(request, 'website/courses.html', context)