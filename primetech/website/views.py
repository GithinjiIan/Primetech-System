from django.shortcuts import render, redirect, get_object_or_404
import json
from .models import Course, CourseCategory, Testimonial, Statistic, CourseApplication
from .forms import CourseApplicationForm
from django.contrib import messages
from django.views.decorators.http import require_POST


def newsletter_signup(request):
    if request.method == 'POST':
        email = request.POST.get('email', '')
        # Save to database or integrate mailchimp later
        messages.success(request, "Thank you for subscribing!")
    return redirect('home')


def home_view(request):
    """Render the homepage with static content."""
    statistics = Statistic.objects.all()
    context = {
        'statistics': statistics,
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


# views.py — Django view for the courses page

def courses(request):
    """Display courses filtered by optional category query parameter."""
    category_slug = request.GET.get('category', None)

    courses = Course.objects.filter(is_active=True).select_related('category')
    if category_slug:
        courses = courses.filter(category__slug=category_slug)

    categories = CourseCategory.objects.all()
    testimonials = Testimonial.objects.filter(is_active=True)

    # Serialize course data to JSON for JavaScript detail population
    courses_dict = {}
    for course in courses:
        courses_dict[str(course.id)] = {
            'title': course.title,
            'description': course.description,
            'duration': course.duration,
            'schedule': course.schedule,
            'instructor': course.instructor,
            'price': course.price,
            'requirements': course.requirements,
            'outcomes': course.outcomes,
        }

    # Application form
    application_form = CourseApplicationForm()

    context = {
        'courses': courses,
        'categories': categories,
        'testimonials': testimonials,
        'courses_json': json.dumps(courses_dict),
        'application_form': application_form,
    }
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
    else:
        messages.error(request, 'Please correct the errors below.')

    return redirect('courses')